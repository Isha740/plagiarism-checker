import re
from difflib import SequenceMatcher

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

import config
from . import semantic

TOKEN_RE = re.compile(r"[a-z0-9']+")
SENT_SPLIT = re.compile(r'(?<=[.!?])\s+(?=["\'(\[]?[A-Z0-9])')
CHUNK = 256  # sentences processed per block (keeps memory flat for long documents)


def tokenize(s):
    return TOKEN_RE.findall(s.lower())


def split_sentences(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for part in SENT_SPLIT.split(line):
            words = part.split()
            for i in range(0, len(words), config.MAX_SENT_WORDS):
                piece = " ".join(words[i:i + config.MAX_SENT_WORDS])
                if len(tokenize(piece)) >= config.MIN_SENT_WORDS:
                    out.append(piece)
    return out


def shingles(tokens, n=None):
    n = n or config.SHINGLE_N
    if len(tokens) < n:
        return {hash(tuple(tokens))} if tokens else set()
    return {hash(tuple(tokens[i:i + n])) for i in range(len(tokens) - n + 1)}


def prepare(row):
    toks = tokenize(row["text"])
    return {"id": row["id"], "name": row["name"], "tokens": toks,
            "shingles": shingles(toks), "sentences": split_sentences(row["text"])}


def _combine(factors, weights):
    keys = [k for k in weights if k in factors]
    total = sum(weights[k] for k in keys)
    return sum(weights[k] * factors[k] for k in keys) / total if total else 0.0


# ----------------------------------------------------------------------------- helpers
def _doc_cosine(udocs):
    n = len(udocs)
    texts = [" ".join(d["tokens"]) for d in udocs]
    try:
        vec = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2), stop_words="english",
                              token_pattern=r"[a-z0-9']+", dtype=np.float32)
        X = vec.fit_transform(texts)
        return (X @ X.T).toarray()
    except ValueError:  # empty vocabulary
        return np.zeros((n, n), dtype=np.float32)


def _sent_sims(rows, S, E, So, Eo):
    lex = (S[rows] @ So.T).toarray() if S is not None else np.zeros((len(rows), So.shape[0]), np.float32)
    if E is not None:
        sem = np.clip(E[rows] @ Eo.T, 0, 1)
        w = config.SENT_SEM_WEIGHT
        return (1 - w) * lex + w * sem
    return lex


def _row_factors(a_text, b_text, ia, ib, S, E):
    ta, tb = tokenize(a_text), tokenize(b_text)
    cos = float((S[ia] @ S[ib].T).toarray()[0, 0]) if S is not None else 0.0
    n = 2 if min(len(ta), len(tb)) < 8 else config.SHINGLE_N
    sa, sb = shingles(ta, n), shingles(tb, n)
    overlap = len(sa & sb) / len(sa) if sa else 0.0
    seq = SequenceMatcher(None, ta, tb, autojunk=False).ratio()
    f = {"cosine": cos, "phrase_overlap": overlap, "sequence": seq}
    if E is not None:
        f["semantic"] = float(np.clip(E[ia] @ E[ib], 0, 1))
    return f


# ----------------------------------------------------------------------------- main entry
def compare(targets, others):
    """Compare every doc in `targets` with every doc in `others` (a doc is never compared with itself).

    Returns {target_id: {"pairs": [...best first...], "rows": [top passages]}} with all values in 0..1.
    """
    union = {}
    for d in list(targets) + list(others):
        union.setdefault(d["id"], d)
    udocs = list(union.values())
    uidx = {d["id"]: i for i, d in enumerate(udocs)}

    # --- document level
    D = _doc_cosine(udocs)

    # --- sentence level
    all_sents, sent_start = [], {}
    for d in udocs:
        sent_start[d["id"]] = len(all_sents)
        all_sents.extend(d["sentences"])
    S = None
    if all_sents:
        try:
            S = TfidfVectorizer(sublinear_tf=True, ngram_range=(1, 2), stop_words="english",
                                token_pattern=r"[a-z0-9']+", dtype=np.float32).fit_transform(all_sents)
        except ValueError:
            S = None
    E = semantic.encode(all_sents) if all_sents else None
    Dsem = None
    if E is not None:
        means = np.zeros((len(udocs), E.shape[1]), np.float32)
        for d in udocs:
            n = len(d["sentences"])
            if n:
                m = E[sent_start[d["id"]]:sent_start[d["id"]] + n].mean(axis=0)
                means[uidx[d["id"]]] = m / (np.linalg.norm(m) + 1e-9)
        Dsem = np.clip(means @ means.T, 0, 1)

    # columns = every sentence of every "other" doc
    o_idx, col_doc, starts, valid = [], [], [], []
    for j, o in enumerate(others):
        n = len(o["sentences"])
        if n == 0:
            continue
        starts.append(len(o_idx))
        valid.append(j)
        s0 = sent_start[o["id"]]
        o_idx.extend(range(s0, s0 + n))
        col_doc.extend([j] * n)
    o_idx = np.array(o_idx, dtype=np.int64)
    col_doc = np.array(col_doc, dtype=np.int64)
    valid = np.array(valid, dtype=np.int64)
    So = S[o_idx] if (S is not None and len(o_idx)) else None
    Eo = E[o_idx] if (E is not None and len(o_idx)) else None
    use_sent = len(o_idx) > 0 and S is not None

    weights = config.DOC_WEIGHTS_SEM if Dsem is not None else config.DOC_WEIGHTS
    row_weights = config.ROW_WEIGHTS_SEM if E is not None else config.ROW_WEIGHTS
    results = {}

    for t in targets:
        ns = len(t["sentences"])
        best = np.zeros((ns, len(others)), dtype=np.float32)
        cands = []  # (score, local_row, col)
        self_cols = np.zeros(len(o_idx), dtype=bool)
        for j, o in enumerate(others):
            if o["id"] == t["id"]:
                self_cols |= (col_doc == j)

        if ns and use_sent:
            s0 = sent_start[t["id"]]
            for a in range(0, ns, CHUNK):
                b = min(a + CHUNK, ns)
                rows = np.arange(s0 + a, s0 + b)
                sims = _sent_sims(rows, S, E, So, Eo)
                if self_cols.any():
                    sims[:, self_cols] = -1.0
                red = np.maximum.reduceat(sims, starts, axis=1)
                best[a:b, valid] = np.clip(red, 0, 1)
                am = sims.argmax(axis=1)
                sc = sims[np.arange(b - a), am]
                for i in range(b - a):
                    if sc[i] > 0.1:
                        cands.append((float(sc[i]), a + i, int(am[i])))

        # pair table
        pairs = []
        for j, o in enumerate(others):
            if o["id"] == t["id"]:
                continue
            ti, oi = uidx[t["id"]], uidx[o["id"]]
            ts = t["shingles"]
            f = {
                "cosine": float(np.clip(D[ti, oi], 0, 1)),
                "phrase_overlap": (len(ts & o["shingles"]) / len(ts)) if ts else 0.0,
                "sentence_match": float((best[:, j] >= config.SENT_MATCH_THRESHOLD).mean()) if ns else 0.0,
            }
            if Dsem is not None:
                f["semantic"] = float(Dsem[ti, oi])
            pairs.append({"other_id": o["id"], "other_name": o["name"],
                          "factors": f, "score": _combine(f, weights)})
        pairs.sort(key=lambda p: p["score"], reverse=True)

        # top passages: shortlist by sentence similarity, then re-score with all factors
        cands.sort(reverse=True)
        rows_out = []
        for sc, r, col in cands[:10]:
            o = others[int(col_doc[col])]
            gi = sent_start[t["id"]] + r
            gj = int(o_idx[col])
            a_text, b_text = all_sents[gi], all_sents[gj]
            f = _row_factors(a_text, b_text, gi, gj, S, E)
            rows_out.append({"text": a_text, "match_text": b_text,
                             "other_id": o["id"], "other_name": o["name"],
                             "factors": f, "score": _combine(f, row_weights)})
        rows_out.sort(key=lambda x: x["score"], reverse=True)
        results[t["id"]] = {"pairs": pairs, "rows": rows_out[:config.TOP_ROWS]}
    return results
