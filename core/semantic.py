"""Optional semantic model hook.

If a sentence-transformers model folder exists at config.SEMANTIC_MODEL_DIR (e.g. the one you train on
Kaggle and download), the engine automatically uses it to catch paraphrased copying.
Without it, the checker runs purely on lexical methods and everything still works.
"""
import os

import numpy as np

import config

_model = None
_tried = False


def _load():
    global _model, _tried
    if _tried:
        return
    _tried = True
    if not config.USE_SEMANTIC or not os.path.isdir(config.SEMANTIC_MODEL_DIR):
        return
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(config.SEMANTIC_MODEL_DIR)
        print(f"[semantic] loaded model from {config.SEMANTIC_MODEL_DIR}")
    except Exception as exc:  # missing package, bad folder, ...
        print(f"[semantic] model not loaded: {exc}")
        _model = None


def available() -> bool:
    _load()
    return _model is not None


def encode(sentences):
    """Return an (N, d) float32 array of L2-normalised embeddings, or None if no model is available."""
    if not sentences or not available():
        return None
    emb = _model.encode(sentences, batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(emb, dtype=np.float32)
