import os
import time
import uuid

from flask import Flask, g, jsonify, request, send_from_directory

import config
from core import db, engine, extract, semantic

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024  # whole request; per-file limit is checked below
db.init()

MODES = ("compare", "reference")


# ------ workspace cookie
def wid():
    w = request.cookies.get("wid")
    if not w or len(w) != 32 or not w.isalnum():
        w = uuid.uuid4().hex
        g.new_wid = w
    return w


@app.after_request
def set_cookie(resp):
    if getattr(g, "new_wid", None):
        resp.set_cookie("wid", g.new_wid, max_age=60 * 60 * 24 * 30, httponly=True, samesite="Lax")
    return resp


def err(msg, code=400):
    return jsonify({"error": msg}), code


def pct(x):
    return round(float(x) * 100, 1)


def pct_factors(f):
    return {k: pct(v) for k, v in f.items()}


def limits(mode):
    return {"max_docs": config.MAX_DOCS[mode], "max_file_mb": config.MAX_FILE_MB,
            "max_words": config.MAX_WORDS_PER_DOC, "extensions": sorted(config.ALLOWED_EXT),
            "min_docs_to_compare": 2 if mode == "compare" else 1}


# ------ pages / state
@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/state")
def state():
    mode = request.args.get("mode")
    if mode not in MODES:
        return err("Unknown mode")
    w = wid()
    docs = db.list_docs(w, mode, "doc")
    ref = db.list_docs(w, mode, "ref")
    return jsonify({"docs": docs, "ref": ref[0] if ref else None, "limits": limits(mode),
                    "semantic_model": semantic.available()})


# ------- upload / delete
@app.post("/api/upload")
def upload():
    mode, kind = request.form.get("mode"), request.form.get("kind")
    if mode not in MODES or kind not in ("doc", "ref"):
        return err("Unknown mode or kind")
    w = wid()
    files = request.files.getlist("files")
    if not files:
        return err("No files received")
    if kind == "ref" and len(files) > 1:
        return err("Upload one reference document at a time")

    existing = {d["name"] for d in db.list_docs(w, mode, "doc")}
    room = config.MAX_DOCS[mode] - db.count_docs(w, mode, "doc")
    added, errors = [], []
    for f in files:
        name = os.path.basename(f.filename or "")
        ext = os.path.splitext(name)[1].lower()
        if ext not in config.ALLOWED_EXT:
            errors.append(f"{name}: only .txt, .pdf and .docx files are supported")
            continue
        data = f.read()
        if len(data) > config.MAX_FILE_MB * 1024 * 1024:
            errors.append(f"{name}: larger than {config.MAX_FILE_MB} MB")
            continue
        if kind == "doc":
            if name in existing:
                errors.append(f"{name}: already uploaded")
                continue
            if room <= 0:
                errors.append(f"{name}: the limit of {config.MAX_DOCS[mode]} documents is reached")
                continue
        try:
            text = extract.extract_text(name, data)
        except Exception:
            errors.append(f"{name}: could not read this file (is it scanned or damaged?)")
            continue
        words = len(engine.tokenize(text))
        if words < config.MIN_WORDS:
            errors.append(f"{name}: contains too little text ({words} words)")
            continue
        if words > config.MAX_WORDS_PER_DOC:
            errors.append(f"{name}: too long ({words} words, max {config.MAX_WORDS_PER_DOC})")
            continue
        if kind == "ref":
            db.delete_kind(w, mode, "ref")  # a mode has a single reference document
        doc_id = db.add_doc(w, mode, kind, name, text, words)
        added.append({"id": doc_id, "name": name, "words": words})
        if kind == "doc":
            existing.add(name)
            room -= 1
    db.purge_old()
    return jsonify({"added": added, "errors": errors})


@app.delete("/api/docs/<int:doc_id>")
def delete(doc_id):
    if not db.delete_doc(wid(), doc_id):
        return err("Document not found", 404)
    return jsonify({"ok": True})


# ------ compare
def _pair_view(p):
    return {"other_id": p["other_id"], "other_name": p["other_name"],
            "score": pct(p["score"]), "factors": pct_factors(p["factors"])}


def _row_view(r):
    return {"text": r["text"], "match_text": r["match_text"], "other_id": r["other_id"],
            "other_name": r["other_name"], "score": pct(r["score"]), "factors": pct_factors(r["factors"])}


@app.post("/api/compare")
def compare():
    body = request.get_json(silent=True) or {}
    mode = body.get("mode")
    use_ref = bool(body.get("use_ref"))
    if mode not in MODES:
        return err("Unknown mode")
    w = wid()
    rows = db.list_docs(w, mode, "doc", with_text=True)
    ref_rows = db.list_docs(w, mode, "ref", with_text=True)

    if mode == "compare":
        if len(rows) < 2:
            return err("Upload at least 2 documents to compare them.")
        if use_ref and not ref_rows:
            return err("Upload a reference document or switch the reference option off.")
    else:
        if not ref_rows:
            return err("Upload a reference document first.")
        if not rows:
            return err("Upload at least 1 assignment document.")
        use_ref = True

    t0 = time.time()
    docs = [engine.prepare(r) for r in rows]
    ref = engine.prepare(ref_rows[0]) if (use_ref and ref_rows) else None
    out = {"mode": mode, "use_ref": use_ref, "semantic_model": semantic.available(), "table": [], "ref_table": []}

    pool = engine.compare(docs, docs) if mode == "compare" else None
    ref_res = engine.compare(docs, [ref]) if ref else None

    for d in docs:
        if pool is not None:
            pairs = pool[d["id"]]["pairs"]
            best = pairs[0] if pairs else None
            entry = {"doc_id": d["id"], "name": d["name"],
                     "best": _pair_view(best) if best else None}
            if ref_res:
                entry["ref_score"] = pct(ref_res[d["id"]]["pairs"][0]["score"])
            out["table"].append(entry)
        if ref_res:
            rp = ref_res[d["id"]]["pairs"][0]
            out["ref_table"].append({"doc_id": d["id"], "name": d["name"], "score": pct(rp["score"]),
                                     "factors": pct_factors(rp["factors"])})
    if pool is not None:
        out["table"].sort(key=lambda e: (e["best"]["score"] if e["best"] else 0), reverse=True)
    out["ref_table"].sort(key=lambda e: e["score"], reverse=True)
    if ref:
        out["ref_name"] = ref["name"]
    out["elapsed"] = round(time.time() - t0, 2)
    return jsonify(out)


if __name__ == "__main__":
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 5000)), debug=False)
