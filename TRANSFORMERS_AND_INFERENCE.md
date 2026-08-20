Transformers & Inference — Quick Reference
=========================================

This document explains the role of Hugging Face `transformers`, the `huggingface-hub` "inference" extra, and the common packages used for local inference and embeddings. Use this to decide which packages to install and how to configure your environment.

1) Key concepts
----------------
- `transformers`: Main HF library for model architectures, pipelines, tokenizers, training and inference utilities. Required to run models locally (CPU/GPU).
- `huggingface-hub`: Client to download and publish models/datasets. It may declare extras like `[inference]` which are convenience groups for related packages.
- `sentence-transformers`: Lightweight library for embeddings (BGE, SBERT families). Used here for embedding generation.
- `accelerate`: Runtime helpers for optimized multi-GPU / mixed-precision execution.
- `safetensors`: Faster and safer model weights format (recommended when available).

2) Two installation strategies
----------------------------

Option A — Explicit (recommended for reproducible projects)
- Install only the packages you need, pin versions, and add them to `requirements.txt`.
- Typical list for local inference + embeddings:

```text
transformers
accelerate
safetensors
tokenizers
sentencepiece
sentence-transformers
huggingface-hub>=0.13.0
```

Pros: explicit control, fewer surprises, easier to pin exact versions.
Cons: you must list every package you need.

Option B — Extra meta-package (convenient)
- Install `huggingface-hub[inference]` which (in some releases) pulls a curated inference stack.
- Example:

```powershell
pip install "huggingface-hub[inference]"
```

Pros: single install command.
Cons: extras vary by `huggingface-hub` version; older releases may not provide the `inference` extra and you'll see warnings like "does not provide the extra 'inference'".

3) Which to choose?
--------------------
- If you plan to run models locally (embeddings or lightweight LLMs) or run evaluation pipelines, choose Option A.
- If you only call remote LLM APIs (Groq, OpenAI) and don't need local model code, you can skip installing `transformers` and related runtime deps.

4) Recommended install commands (explicit)
-----------------------------------------

Run in your activated virtualenv:

```powershell
pip install -U pip setuptools wheel
pip install -U transformers accelerate safetensors tokenizers sentencepiece sentence-transformers huggingface-hub
```

Or add to `requirements.txt` (explicit pins optional):

```text
transformers>=4.35.0
accelerate>=0.21.0
safetensors>=0.3.0
tokenizers>=0.14.0
sentencepiece>=0.1.98
sentence-transformers>=2.2.2
huggingface-hub>=0.13.0
```

5) Quick runtime checks
-----------------------
- Check versions:

```powershell
python -c "import transformers, accelerate, safetensors, sentence_transformers, huggingface_hub; print(transformers.__version__, accelerate.__version__, huggingface_hub.__version__)"
```

- Small example: get an embedding via `sentence-transformers`:

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
vec = model.encode('hello world', normalize_embeddings=True)
print(len(vec))
```

6) Troubleshooting
------------------
- Warning "huggingface-hub X.Y does not provide the extra 'inference'": upgrade `huggingface-hub` or install explicit inference deps.
- Install failures on Windows for `faiss-cpu` or `safetensors` may require platform-specific wheels — see project docs or use conda for CPU/GPU builds.
- If you see import errors after editing `requirements.txt`, re-run:

```powershell
pip install -r requirements.txt
```

7) Notes for this repository
---------------------------
- This project currently uses `sentence-transformers` for embeddings (BGE model); if you plan to perform local semantic search or run local LLMs, install the above inference stack.
- If you want me to update `requirements.txt` to add the explicit inference packages, I can do that and run a quick import check for you.

8) Next steps
-------------
- Tell me whether you want the explicit install (Option A) added to `requirements.txt` (recommended). If yes, I will update the file and run a validation import.
- Or I can add `huggingface-hub[inference]` to `requirements.txt` instead.

---
Generated on May 2, 2026.
