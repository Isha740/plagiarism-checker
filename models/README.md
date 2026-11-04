# Models

The app runs without any model. Two optional deep-learning models improve detection of **paraphrased** text.
Both start from pretrained networks and are fine-tuned on Kaggle (GPU). Folders are detected automatically at start-up.

| Folder | Model | Role | Notebook |
|---|---|---|---|
| `models/semantic/` | MiniLM bi-encoder (`all-MiniLM-L6-v2`, fine-tuned) | Turns each sentence into a vector; finds sentences with similar meaning fast | `kaggle/train_semantic_model.ipynb` |
| `models/verifier/` | Cross-encoder (`distilroberta-base`, fine-tuned) | Reads two sentences together and decides if they truly mean the same | `kaggle/train_crossencoder_verifier.ipynb` |

## Why two models
A bi-encoder is fast because each sentence is encoded once, but it never sees both sentences together, so it
struggles when two sentences share words but differ in meaning ("flights from NY to Florida" vs the reverse).
A cross-encoder is more accurate but slow. So the app uses both: fast methods shortlist candidate pairs,
and the cross-encoder verifies only those.

## Training data (label 1 = same meaning)
- PAWS – word-swap pairs with very high overlap (teaches the model not to trust overlap)
- MRPC – news paraphrases
- QQP – duplicate questions (40,000-pair subset)

## How to train (Kaggle)
1. Create a Kaggle notebook and import the `.ipynb` file.
2. Settings: Accelerator = GPU T4, Internet = On (phone-verified account).
3. Run All. Download the output zip (`semantic.zip` or `crossenc.zip`) and the metrics JSON.

## How to install the trained models
1. Unzip `semantic.zip` into `models/semantic/` so `models/semantic/config.json` exists.
2. Unzip `crossenc.zip` into `models/verifier/` so `models/verifier/config.json` and `threshold.json` exist.
3. `pip install sentence-transformers` (installs torch and transformers).
4. Restart the app. The terminal prints `[semantic] loaded model …` and `[verifier] loaded cross-encoder …`.

Switch off: `PC_USE_SEMANTIC=0`, `PC_USE_VERIFIER=0`. Custom folders: `PC_SEMANTIC_MODEL`, `PC_VERIFIER_MODEL`.

## How the app uses them
1. Word matching and MiniLM compute sentence similarities.
2. A sentence pair is shortlisted if max(word similarity, MiniLM similarity) ≥ `VERIFY_PREFILTER` (0.50).
3. The cross-encoder scores up to `MAX_VERIFY_PAIRS` (2000) shortlisted pairs, most similar first.
4. A pair is a match if the cross-encoder probability ≥ the threshold in `threshold.json`.
   Near-identical sentences (word similarity ≥ `NEAR_VERBATIM`, 0.90) are accepted without the check.
5. Without the verifier, MiniLM alone is used: a sentence matches if its cosine ≥ `SEM_MATCH_THRESHOLD` (0.75).

## Results
| Model | Threshold | Accuracy | Precision | Recall | F1 | AUC |
|---|---:|---:|---:|---:|---:|---:|
| TF-IDF cosine baseline | 0.15 | 0.498 | 0.481 | 0.991 | 0.647 | 0.564 |
| MiniLM, not fine-tuned | 0.74 | 0.539 | 0.502 | 0.939 | 0.655 | 0.589 |
| MiniLM, fine-tuned | 0.69 | 0.743 | 0.693 | 0.801 | 0.743 | 0.811 |
| Fine-tuned cross-encoder (verifier) @ best-F1 threshold | 0.49 | 0.8912 | 0.8592 | 0.916 | 0.8867 | 0.9549 |
| Fine-tuned cross-encoder (verifier) @ strict threshold | 0.34 | 0.8878 | 0.8422 | 0.9338 | 0.8856 | 0.9549 |

The baselines are near chance because PAWS pairs all overlap heavily; that does not mean word matching fails on
ordinary copy-paste, which is a different, easier task.

## Tuning
- Too many false alarms → raise `SEM_MATCH_THRESHOLD` or use `strict_threshold` from `threshold.json` as `threshold`.
- Paraphrases missed → lower them by about 0.05.
- Slow on CPU → lower `MAX_VERIFY_PAIRS` or `MAX_DOCS` in `config.py`.