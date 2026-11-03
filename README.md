# Markup - online plagiarism checker

Two modes in one web app (Flask + vanilla JS, no build step):

1. **Compare documents with each other** - upload one or many documents (needs at least 2 in the database).
   One table: document, max similarity %, the document it matches most, and (optional toggle) similarity with a
   reference document. Turn the toggle on and upload one reference to add that last column.
2. **Check against a reference document** - upload a reference and the assignments; assignments are compared only
   with the reference. One table: document and its similarity % with the reference.

In the comparison option a dropdown (or a click on a row) shows the selected document's max similarity %, the factors
behind it, and the document it matches. Uploaded files are listed and can be deleted.

## Run it
    python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    python app.py                                         # open http://127.0.0.1:5000
    python tests/smoke_test.py                            # optional end-to-end check (uses samples/)
    python tests/benchmark.py 2000                        # optional speed test

Set HOST=0.0.0.0 PORT=8000 to serve on a network. For production use `gunicorn -w 2 app:app`.

## How many documents? (set in config.py)
Compare mode does n(n-1)/2 comparisons, so time grows quickly; reference mode grows linearly.
Measured on this engine (no trained model, one CPU, synthetic text):

| docs | pairs  | 1,000 words each | 3,000 words each |
|-----:|-------:|-----------------:|-----------------:|
| 25   | 300    | 0.2 s | 0.9 s |
| 50   | 1,225  | 0.6 s | 2.8 s |
| 100  | 4,950  | 1.9 s | 9.9 s |
| 200  | 19,900 | 6.3 s | 42.6 s |

Defaults: 50 documents in compare mode, 100 in reference mode, 5 MB / 20,000 words per file.
Your server will differ - run tests/benchmark.py and adjust MAX_DOCS.

## How the score works
Percentages are from the first document's point of view (how much of it appears in the other text).
- Word cosine - TF-IDF cosine of the whole texts (shared vocabulary/topic)
- Phrase overlap - share of 3-word phrases also found in the other text (copied wording)
- Sentences matched - share of sentences with a close match (>= 70%) in the other text
- Word order (passages) - order-aware match ratio
- Meaning / Semantic - only when a trained model is installed (see models/README.md)

Final % = weighted mean (weights in config.py). Bars: green < 30%, amber 30-60%, red > 60%.
A high score means "look at this", not proof of plagiarism: shared quotes, citations and common phrasing also count.

## Privacy and structure
- Each browser gets a private workspace (cookie); users can't see each other's files. Documents are auto-deleted after 24 h.
- No login yet - add authentication before public hosting.

    app.py            Flask routes (state, upload, delete, compare)
    config.py         limits, weights, thresholds
    core/engine.py    similarity engine       core/extract.py  txt/pdf/docx reader
    core/db.py        SQLite storage          core/semantic.py optional Kaggle model hook
    static/           index.html, style.css, app.js
    samples/          demo files              tests/           smoke test + benchmark
    models/README.md  how to integrate the Kaggle model

Scanned (image-only) PDFs have no text and are rejected; OCR would be a later addition.

## Deep learning part (Kaggle)
`kaggle/train_semantic_model.ipynb` fine-tunes the pretrained `all-MiniLM-L6-v2` on PAWS + MRPC + QQP, compares it with
the TF-IDF baseline, and exports `semantic.zip`. Unzip it into `models/semantic/`, run `pip install sentence-transformers`,
restart the app, and the "Meaning" factor is used automatically. Details in `models/README.md`.
