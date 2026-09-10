from sentence_transformers import SentenceTransformer
import numpy as np
from app.services.memory_diagnostics import log_memory

# Module-level singleton
# Loads ONCE when module is first imported
_model = None


def get_embedding_model() -> SentenceTransformer:
    """
    Returns singleton embedding model.
    Loads on first call, reuses on subsequent calls.
    Thread-safe for FastAPI async context.
    """
    global _model
    if _model is None:
        print("[Embeddings] Loading BAAI/bge-base-en-v1.5...")
        log_memory("before embedding model load")
        _model = SentenceTransformer("BAAI/bge-base-en-v1.5")
        log_memory("after embedding model load")
        print("[Embeddings] Model loaded and ready")
    return _model


def embed_text(text: str) -> np.ndarray:
    """
    Embed a single text string.
    Returns normalized float32 array of shape (768,)
    normalize_embeddings=True improves cosine similarity search.
    """
    model = get_embedding_model()
    embedding = model.encode(
        text,
        normalize_embeddings=True
    )
    return embedding.astype(np.float32)


def embed_batch(texts: list) -> np.ndarray:
    """
    Embed a list of texts efficiently.
    Returns normalized float32 array of shape (n, 768)
    """
    model = get_embedding_model()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True,
        batch_size=32
    )
    return embeddings.astype(np.float32)
