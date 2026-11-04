import os, random, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import engine  # noqa: E402

random.seed(1)
VOCAB = [f"w{i}" for i in range(6000)]
WEIGHTS = [1 / (i + 1) for i in range(len(VOCAB))]


def make_sentence():
    return " ".join(random.choices(VOCAB, WEIGHTS, k=random.randint(10, 20))).capitalize() + "."


def make_docs(n, words):
    pool = [make_sentence() for _ in range(300)]   # shared sentences -> realistic copying
    docs = []
    for i in range(n):
        sents, count = [], 0
        while count < words:
            s = random.choice(pool) if random.random() < 0.1 else make_sentence()
            sents.append(s); count += len(s.split())
        text = " ".join(sents)
        docs.append(engine.prepare({"id": i, "name": f"d{i}", "text": text}))
    return docs


if __name__ == "__main__":
    words = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    print(f"{words} words per document")
    for n in (10, 25, 50, 100, 200):
        docs = make_docs(n, words)
        t = time.time(); engine.compare(docs, docs); dt = time.time() - t
        print(f"  {n:4d} docs ({n*(n-1)//2:6d} pairs): {dt:6.2f}s")
