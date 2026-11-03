"""End-to-end check through the real HTTP API. Run:  python tests/smoke_test.py"""
import io, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["PC_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "test.db")
import app as appmod  # noqa: E402

S = os.path.join(os.path.dirname(__file__), "..", "samples")
c = appmod.app.test_client()


def up(mode, kind, names):
    files = [(open(os.path.join(S, n), "rb"), n) for n in names]
    return c.post("/api/upload", data={"mode": mode, "kind": kind, "files": files},
                  content_type="multipart/form-data").get_json()


print("compare with 1 doc ->", c.post("/api/compare", json={"mode": "compare"}).get_json())
print(up("compare", "doc", ["essay_a.txt"]))
print("compare with 1 doc ->", c.post("/api/compare", json={"mode": "compare"}).get_json())
print(up("compare", "doc", ["essay_b.txt", "essay_c.txt", "essay_a.txt"]))  # last one is a duplicate
print(up("compare", "kind" and "ref", ["reference.txt"]))
r = c.post("/api/compare", json={"mode": "compare", "use_ref": True}).get_json()
for e in r["table"]:
    print(f"{e['name']:14} best {e['best']['score']:5}% -> {e['best']['other_name']:14} ref {e['ref_score']}%")
print("elapsed", r["elapsed"])

print(up("reference", "ref", ["reference.txt"]))
print(up("reference", "doc", ["essay_a.txt", "essay_b.txt", "essay_c.txt"]))
r = c.post("/api/compare", json={"mode": "reference"}).get_json()
for e in r["ref_table"]:
    print(f"{e['name']:14} {e['score']:5}%  {e['factors']}")
state = c.get("/api/state?mode=reference").get_json()
did = state["docs"][0]["id"]
print("delete ->", c.delete(f"/api/docs/{did}").get_json(), "| left:", len(c.get('/api/state?mode=reference').get_json()["docs"]))
