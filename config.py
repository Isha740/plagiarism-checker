"""Central settings. Change limits here (or override with environment variables)."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("PC_DB_PATH", os.path.join(BASE_DIR, "data", "plagiarism.db"))

# ---- Limits (see README "How many documents?") -------------------------------
# Comparison mode is document-vs-document, so work grows with n*(n-1)/2.
# Reference mode only compares against one document, so work grows with n.
MAX_DOCS = {"compare": int(os.environ.get("PC_MAX_DOCS_COMPARE", 50)),
            "reference": int(os.environ.get("PC_MAX_DOCS_REFERENCE", 100))}
MAX_FILE_MB = 5               # per uploaded file
MIN_WORDS = 20                # documents with less text are rejected
MAX_WORDS_PER_DOC = 20000     # ~40 pages
ALLOWED_EXT = {".txt", ".pdf", ".docx"}
PURGE_AFTER_HOURS = 24        # uploaded docs are removed automatically after this

# ---- Text processing -------------------------------------------------------
MIN_SENT_WORDS = 5            # shorter sentences are ignored
MAX_SENT_WORDS = 45           # very long unpunctuated runs are cut into pieces
SHINGLE_N = 3                 # word n-gram size for "phrase overlap"
SENT_MATCH_THRESHOLD = 0.70   # a sentence counts as "matched" at/above this similarity
TOP_ROWS = 3                  # passages shown per document

# ---- Scoring weights ---------------------------------------------------------
# Document level (each factor is 0..1, final score is the weighted mean)
DOC_WEIGHTS = {"cosine": 0.25, "phrase_overlap": 0.35, "sentence_match": 0.40}
DOC_WEIGHTS_SEM = {"cosine": 0.15, "phrase_overlap": 0.25, "sentence_match": 0.30, "semantic": 0.30}
# Passage (row) level
ROW_WEIGHTS = {"cosine": 0.35, "phrase_overlap": 0.25, "sequence": 0.40}
ROW_WEIGHTS_SEM = {"cosine": 0.25, "phrase_overlap": 0.15, "sequence": 0.25, "semantic": 0.35}
# How much the semantic model contributes to sentence-to-sentence similarity (if a model is installed)
SENT_SEM_WEIGHT = 0.5

# ---- Optional trained model (Kaggle) ----------------------------------------
SEMANTIC_MODEL_DIR = os.environ.get("PC_SEMANTIC_MODEL", os.path.join(BASE_DIR, "models", "semantic"))
USE_SEMANTIC = os.environ.get("PC_USE_SEMANTIC", "1") == "1"
