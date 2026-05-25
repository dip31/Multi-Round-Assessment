import faiss
import numpy as np
import json
import logging
import os
from app.services.embedding_service import embed_text

rag_logger = logging.getLogger("rag_pipeline")

# Module-level singletons — load ONCE
_index = None
_metadata = None


def load_kb():
    """
    Load FAISS index and metadata.
    Singleton: loads once, reuses on all subsequent calls.
    """
    global _index, _metadata
    if _index is None:
        index_path = "app/data/kb.index"
        meta_path = "app/data/kb_metadata.json"

        if not os.path.exists(index_path):
            raise FileNotFoundError(
                f"KB index not found at {index_path}. "
                "Run: python scripts/build_kb_index.py"
            )

        print("[Retriever] Loading FAISS index...")
        _index = faiss.read_index(index_path)
        with open(meta_path) as f:
            _metadata = json.load(f)
        print(f"[Retriever] Loaded {_index.ntotal} vectors")

    return _index, _metadata


def keyword_score(query: str, doc_text: str) -> float:
    """
    Simple keyword overlap score.
    Returns fraction of query words found in document.
    """
    query_words = set(query.lower().split())
    doc_words = set(doc_text.lower().split())
    if not query_words:
        return 0.0
    overlap = len(query_words & doc_words)
    return overlap / len(query_words)


def hybrid_score(
    embedding_score: float,
    query: str,
    doc_text: str,
    doc_role: str,
    detected_role: str
) -> float:
    """
    Combines embedding similarity + keyword overlap + role boost.
    
    Formula:
      final = 0.7 * embedding + 0.3 * keyword + role_boost
    
    Role boost: 0.2 if doc role matches detected role
    This replaces hard role filtering — allows
    cross-domain questions while prioritizing role match.
    """
    kw = keyword_score(query, doc_text)
    role_boost = 0.2 if doc_role == detected_role else 0.0
    return (0.7 * embedding_score) + (0.3 * kw) + role_boost


def build_query(
    skills: list,
    projects: dict | list,
    detected_role: str
) -> str:
    """
    Build rich contextual query for semantic search.
    NOT just keywords — full contextual description.
    This significantly improves retrieval relevance.
    """
    if isinstance(projects, dict):
        project_texts = list(projects.values())[:3]
    elif isinstance(projects, list):
        project_texts = projects[:3]
    else:
        project_texts = []

    skills_text = ", ".join(skills[:10])
    projects_text = ". ".join([str(p) for p in project_texts])

    return f"""
      Candidate Skills: {skills_text}
      Projects: {projects_text}
      Target Role: {detected_role}
      Interview knowledge needed for technical assessment
      of {detected_role} candidate.
      """.strip()


def retrieve(
    skills: list,
    projects: dict | list,
    detected_role: str,
    k: int = 8,
    final_k: int = 5
) -> list:
    """
    Full hybrid RAG retrieval pipeline:
    
    1. Build contextual query
    2. Embed query (BGE model)
    3. FAISS vector search (k=8, over-fetch)
    4. Compute hybrid score per result
    5. Sort by hybrid score
    6. Return top final_k
    
    NO hard role filtering — uses score boosting instead.
    Fallback: if < 3 results, relaxes to all retrieved docs.
    """
    index, metadata = load_kb()

    # Step 1+2: Build and embed query
    query = build_query(skills, projects, detected_role)
    query_embedding = embed_text(query).reshape(1, -1)

    # Step 3: Vector search (fetch more than needed)
    distances, indices = index.search(query_embedding, k)

    # Step 4: Fetch docs and compute hybrid scores
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        doc = metadata.get(str(idx))
        if not doc:
            continue

        doc = dict(doc)  # copy to avoid mutating metadata
        doc["embedding_score"] = float(dist)
        doc["final_score"] = hybrid_score(
            float(dist),
            query,
            doc.get("text", ""),
            doc.get("role", ""),
            detected_role
        )
        results.append(doc)

    # Step 5: Sort by hybrid score descending
    results.sort(
        key=lambda x: x["final_score"],
        reverse=True
    )

    # Step 6: Return top final_k
    top_results = results[:final_k]

    # Retrieval logging — for observability and viva demo
    rag_logger.info(
        f"[RAG Retrieval] "
        f"role={detected_role} | "
        f"fetched={len(results)} | "
        f"returned={len(top_results)} | "
        f"topics={[r.get('topic','?') for r in top_results]} | "
        f"scores={[round(r['final_score'],3) for r in top_results]}"
    )

    return top_results


def format_for_prompt(retrieved_docs: list) -> str:
    """
    Format retrieved documents for LLM prompt injection.
    Clean and structured — no noise.
    Max 5 docs to avoid context overload.
    """
    formatted = []
    for i, doc in enumerate(retrieved_docs[:5]):
        if doc.get("type") == "question":
            entry = (
                f"[{i+1}] {doc.get('difficulty','').upper()} "
                f"Question ({doc.get('topic','')}):\n"
                f"  {doc['text']}"
            )
            if doc.get("expected_points"):
                points = ", ".join(
                    doc["expected_points"][:3]
                )
                entry += f"\n  Key points: {points}"
        else:
            entry = (
                f"[{i+1}] Concept - "
                f"{doc.get('concept_name', doc.get('topic',''))}:\n"
                f"  {doc['text'][:300]}"
            )
            if doc.get("key_points"):
                points = ", ".join(doc["key_points"][:3])
                entry += f"\n  Key points: {points}"

        formatted.append(entry)

    return "\n\n".join(formatted)
