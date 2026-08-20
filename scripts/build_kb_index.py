"""
Run ONCE to build FAISS index from question bank
and concept KB.

Run: python scripts/build_kb_index.py

Outputs:
  app/data/kb.index        (FAISS binary index)
  app/data/kb_metadata.json (document metadata)

Re-run only when question_bank.json or 
concept_kb.json is updated.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)
)))

import faiss
import numpy as np
import json

from app.services.embedding_service import embed_batch


def build_index():
    print("=== Building KB Index ===")

    # Load question bank
    bank_path = "app/data/question_bank.json"
    concept_path = "app/data/concept_kb.json"

    with open(bank_path) as f:
        bank = json.load(f)
    with open(concept_path) as f:
        concepts = json.load(f)

    documents = []

    # Process questions from bank
    for role, difficulties in bank.items():
        for diff, questions in difficulties.items():
            for q in questions:
                if isinstance(q, str):
                    doc = {
                        "id": f"q_{role}_{diff}",
                        "text": q,
                        "role": role,
                        "difficulty": diff,
                        "topic": "general",
                        "type": "question",
                        "expected_points": []
                    }
                else:
                    doc = dict(q)
                    doc["type"] = "question"
                documents.append(doc)

    # Process concepts
    for concept in concepts:
        doc = {
            "id": concept["id"],
            "text": concept["explanation"],
            "role": concept["role"],
            "difficulty": "medium",
            "topic": concept["topic"],
            "type": "concept",
            "concept_name": concept["concept"],
            "key_points": concept.get("key_points", [])
        }
        documents.append(doc)

    print(f"Total documents: {len(documents)}")

    # Build embedding texts
    # Combine text + key points for richer embeddings
    texts = []
    for doc in documents:
        combined = doc["text"]
        if doc.get("expected_points"):
            combined += " " + " ".join(
                doc["expected_points"]
            )
        if doc.get("key_points"):
            combined += " " + " ".join(doc["key_points"])
        texts.append(combined)

    # Generate embeddings
    print("Generating embeddings...")
    embeddings = embed_batch(texts)

    # Build FAISS index
    # IndexFlatIP = inner product (cosine with normalized vecs)
    dimension = embeddings.shape[1]
    print(f"Embedding dimension: {dimension}")
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    print(f"Index built with {index.ntotal} vectors")

    # Save index
    os.makedirs("app/data", exist_ok=True)
    faiss.write_index(index, "app/data/kb.index")
    print("Saved: app/data/kb.index")

    # Save metadata
    metadata = {
        str(i): doc for i, doc in enumerate(documents)
    }
    with open("app/data/kb_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print("Saved: app/data/kb_metadata.json")

    print(f"=== Done. {len(documents)} documents indexed ===")


if __name__ == "__main__":
    build_index()
