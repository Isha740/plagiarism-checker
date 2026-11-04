# Markup – Online Plagiarism Checker

A web application that detects copied and paraphrased text in two ways:

1. **Compare documents with each other** – every uploaded document is compared with all the others.
2. **Check against a reference document** – every assignment is compared only with one reference text.

The system combines classical text matching (TF-IDF, phrase overlap) with two pretrained deep-learning
models fine-tuned on Kaggle: a **bi-encoder** (MiniLM) that understands meaning, and a **cross-encoder**
that verifies whether two sentences really mean the same thing.

---

## Features
- Upload one or many documents (.txt, .pdf, .docx); each option has its own uploaded list with a Delete button.
- Option 1 needs at least 2 documents before Compare is enabled.
- Option 1 table: Document | Max similarity | Most similar to | Similarity with reference (optional toggle).
- A dropdown shows, for a chosen document, its max similarity %, the factors behind it, and the matching document.
- Option 2 table: Document | Similarity with reference.
- Private workspace per browser (cookie); uploads auto-delete after 24 hours.
- Works without any trained model (word-matching only); models add paraphrase detection when installed.

## Technology
Python 3.10+, Flask, SQLite, scikit-learn, pypdf, python-docx, vanilla HTML/CSS/JavaScript.
Optional deep learning: PyTorch, Hugging Face Transformers, sentence-transformers.

## Project structure
```
plagiarism-checker/
├── app.py                  Flask routes: state, upload, delete, compare
├── config.py               limits, thresholds, weights, model paths
├── requirements.txt
├── core/
│   ├── engine.py           similarity engine (all scoring logic)
│   ├── extract.py          text extraction from txt/pdf/docx
│   ├── db.py               SQLite storage
│   ├── semantic.py         optional bi-encoder (MiniLM) loader
│   └── verifier.py         optional cross-encoder loader
├── static/                 index.html, style.css, app.js (user interface)
├── models/
│   ├── semantic/           put the bi-encoder here (from Kaggle)
│   ├── verifier/           put the cross-encoder here (from Kaggle)
│   └── README.md
├── kaggle/
│   ├── train_semantic_model.ipynb
│   └── train_crossencoder_verifier.ipynb
├── samples/                demo documents
├── tests/                  smoke_test.py, benchmark.py
└── data/                   SQLite database is created here
```

## Installation and running
```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                       # open http://127.0.0.1:5000
```
Optional checks: `python tests/smoke_test.py` and `python tests/benchmark.py 2000`.
To use the deep-learning models (after Kaggle training): `pip install sentence-transformers`
(this also installs torch and transformers), then place the model folders as described in `models/README.md`.

Environment variables: `HOST`, `PORT`, `PC_DB_PATH`, `PC_MAX_DOCS_COMPARE`, `PC_MAX_DOCS_REFERENCE`,
`PC_SEMANTIC_MODEL`, `PC_USE_SEMANTIC`, `PC_VERIFIER_MODEL`, `PC_USE_VERIFIER`, `PC_MAX_VERIFY_PAIRS`.

## Limits (config.py)
| Setting | Default |
|---|---|
| Documents, compare option | 50 |
| Documents, reference option | 100 |
| File size | 5 MB |
| Words per document | 20,000 (min 20) |
| Auto-delete after | 24 hours |

Why: comparing every document with every other needs n(n−1)/2 comparisons. Measured without models on one CPU:

| Documents | Pairs | 1,000 words each | 3,000 words each |
|---:|---:|---:|---:|
| 25 | 300 | 0.2 s | 0.9 s |
| 50 | 1,225 | 0.6 s | 2.8 s |
| 100 | 4,950 | 1.9 s | 9.9 s |
| 200 | 19,900 | 6.3 s | 42.6 s |

Models add time (embedding and verification); on CPU-only servers keep 50 or fewer.

## How similarity is computed
Scores are from the first document's point of view ("how much of A appears in B"), so A→B and B→A can differ.

| Factor | Meaning |
|---|---|
| Word cosine | TF-IDF cosine similarity of the full texts |
| Phrase overlap | share of A's 3-word phrases that also occur in B |
| Sentences matched | share of A's sentences with a match in B |
| Meaning (needs models) | share of A's sentences verified as same-meaning in B |

Final % = weighted mean of the factors (weights in `config.py`):
without models 0.25 cosine + 0.35 phrase + 0.40 sentences;
with models 0.15 cosine + 0.25 phrase + 0.30 sentences + 0.30 meaning.
Bar colours: green < 30 %, amber 30–60 %, red > 60 %.

## Deep-learning results
Test set = PAWS + MRPC + QQP (PAWS is deliberately hard: same words, different meaning).

| Model | Accuracy | F1 | AUC |
|---|---:|---:|---:|
| TF-IDF cosine (lexical baseline) | 0.498 | 0.647 | 0.564 |
| Pretrained MiniLM, no fine-tuning | 0.539 | 0.655 | 0.589 |
| Fine-tuned MiniLM (bi-encoder) | 0.743 | 0.743 | 0.811 |
| Fine-tuned cross-encoder (verifier) | _fill in from crossenc_metrics.json_ | | |

## REST API
| Method | Route | Purpose |
|---|---|---|
| GET | `/api/state?mode=` | uploaded documents, reference, limits |
| POST | `/api/upload` | form fields `mode`, `kind` (doc/ref), `files` |
| DELETE | `/api/docs/<id>` | delete one document |
| POST | `/api/compare` | JSON `{mode, use_ref}` → result tables |

## Limitations
- A high percentage means "review this", not proof of plagiarism (quotes and citations also match).
- Scanned PDFs without a text layer are rejected (no OCR).
- Stop-word handling and the models are English-oriented.
- No login system; add authentication and PostgreSQL before public deployment.
- The cross-encoder checks at most `MAX_VERIFY_PAIRS` (default 2000) shortlisted pairs per run.