"""
Semantic chunking + vector search with ChromaDB.
Chunks PDFs semantically, stores embeddings locally, and retrieves relevant clauses
for the selected inspection profile.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from rule_profiles import get_profile
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Local embedding model (runs on CPU, ~100MB download)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
DEFAULT_CHROMA_PERSIST_DIR = Path(__file__).resolve().parents[2] / "data" / "chromadb"
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(DEFAULT_CHROMA_PERSIST_DIR))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))  # characters
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
TOP_K = int(os.getenv("RAG_TOP_K", "5"))


class SemanticRAG:
    """Manages ChromaDB collection and semantic retrieval for PDF documents."""

    def __init__(self):
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        self.chroma_client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.chroma_client.get_or_create_collection(
            name="pdf_chunks",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "RAG initialized: collection=%s, embedding=%s",
            self.collection.name,
            EMBEDDING_MODEL,
        )

    def chunk_text(
        self, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
    ) -> list[str]:
        """
        Split text into overlapping chunks.
        Tries to respect paragraph boundaries; falls back to character splitting.
        """
        if not text or len(text.strip()) < 20:
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]

            # Try to extend to next paragraph break
            if end < text_len:
                next_break = text.find("\n\n", end - overlap)
                if next_break != -1 and next_break - start <= chunk_size + 200:
                    chunk = text[start:next_break]
                    start = next_break
                else:
                    start = end - overlap
            else:
                start = text_len

            chunk = chunk.strip()
            if chunk:
                chunks.append(chunk)

        logger.info("Chunked text into %d chunks", len(chunks))
        return chunks

    def index_document(
        self, doc_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> int:
        """
        Chunk and index a PDF document into ChromaDB.
        Returns the number of chunks indexed.
        """
        chunks = self.chunk_text(text)
        if not chunks:
            return 0

        # Delete existing chunks for this doc_id
        try:
            existing = self.collection.get(where={"doc_id": doc_id})
            if existing["ids"]:
                self.collection.delete(ids=existing["ids"])
        except Exception:
            pass

        # Prepare data
        embeddings = self.embedding_model.encode(chunks).tolist()
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "doc_id": doc_id,
                "chunk_index": i,
                "chunk_length": len(chunk),
                **(metadata or {}),
            }
            for i, chunk in enumerate(chunks)
        ]

        self.collection.add(
            documents=chunks,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas,
        )
        logger.info("Indexed %d chunks for document %s", len(chunks), doc_id)
        return len(chunks)

    def retrieve(
        self,
        query: str,
        top_k: int = TOP_K,
        profile_id: str | None = None,
        doc_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve the most relevant chunks for a query.
        Optionally boost profile-specific keywords.
        """
        # Enhance query with profile-specific terms if available
        enhanced_query = query
        if profile_id:
            try:
                profile = get_profile(profile_id)
                keywords = " ".join(profile.fields)
                enhanced_query = f"{query}\n\nRelevant keywords: {keywords}"
            except ValueError:
                pass

        query_embedding = self.embedding_model.encode([enhanced_query]).tolist()
        query_kwargs = {
            "query_embeddings": query_embedding,
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if doc_id:
            query_kwargs["where"] = {"doc_id": doc_id}

        results = self.collection.query(**query_kwargs)

        retrieved = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                retrieved.append(
                    {
                        "text": doc,
                        "metadata": (
                            results["metadatas"][0][i] if results["metadatas"] else {}
                        ),
                        "distance": (
                            results["distances"][0][i] if results["distances"] else None
                        ),
                    }
                )

        logger.info("Retrieved %d chunks for query", len(retrieved))
        return retrieved

    def get_stats(self) -> dict[str, Any]:
        """Return collection statistics."""
        count = self.collection.count()
        return {"total_chunks": count, "embedding_model": EMBEDDING_MODEL}
