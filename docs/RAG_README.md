RAG (Retrieval-Augmented Generation) Setup
=========================================

Quick steps to prepare RAG components (embeddings + FAISS index) and database migration.

1) Create a Python virtual environment and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\Activate.ps1 on Windows (PowerShell)
pip install -r requirements.txt
```

2) Build the offline KB index (run once or when KB updates)

```bash
python scripts/build_kb_index.py
# Verifies that `app/data/kb.index` and `app/data/kb_metadata.json` exist
```

3) Apply Alembic migrations (adds `detected_role` column)

```bash
alembic upgrade head
```

4) Start the FastAPI server

```bash
uvicorn app.main:app --reload
```

Notes:
- The first run of `sentence-transformers` model will download weights (several hundred MB).
- If `faiss-cpu` installation fails on some platforms, follow platform-specific wheels or use `pip install faiss-cpu -f https://download.pytorch.org/whl/torch_stable.html`.
- The offline index builder uses `app/data/question_bank.json` and `app/data/concept_kb.json`.
