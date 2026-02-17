"""
SQLite vector store service for RAG chunks.

This backend stores chunk metadata/content and embedding vectors in SQLite,
and computes cosine similarity at query time.
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Sequence


logger = logging.getLogger(__name__)


class SqliteVecService:
    """Service for chunk-level vector storage and retrieval in SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from .rag_config_service import RagConfigService

            cfg = RagConfigService().config.storage
            db_path = str(getattr(cfg, "vector_sqlite_path", "data/state/rag_vec.sqlite3"))

        db_path_obj = Path(db_path)
        if not db_path_obj.is_absolute():
            db_path_obj = Path(__file__).parent.parent.parent.parent / db_path_obj
        db_path_obj.parent.mkdir(parents=True, exist_ok=True)

        self.db_path = db_path_obj
        self._lock = Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rag_vec_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    kb_id TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    ingest_id TEXT DEFAULT '',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_vec_kb ON rag_vec_chunks (kb_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_vec_kb_doc ON rag_vec_chunks (kb_id, doc_id)"
            )
            conn.commit()

    @staticmethod
    def _normalize_vector(vector: Sequence[float]) -> List[float]:
        return [float(item) for item in vector]

    @staticmethod
    def _cosine_similarity(query: Sequence[float], candidate: Sequence[float]) -> float:
        if len(query) != len(candidate):
            return 0.0
        dot = 0.0
        q_norm = 0.0
        c_norm = 0.0
        for q_val, c_val in zip(query, candidate):
            dot += q_val * c_val
            q_norm += q_val * q_val
            c_norm += c_val * c_val
        if q_norm <= 0.0 or c_norm <= 0.0:
            return 0.0
        return dot / (math.sqrt(q_norm) * math.sqrt(c_norm))

    def upsert_chunks(
        self,
        *,
        kb_id: str,
        doc_id: str,
        filename: str,
        file_type: str,
        ingest_id: str,
        chunk_rows: List[Dict[str, object]],
    ) -> None:
        """Upsert chunk rows for one document generation."""
        if not chunk_rows:
            return

        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            try:
                for row in chunk_rows:
                    chunk_id = str(row.get("chunk_id") or "")
                    if not chunk_id:
                        continue
                    chunk_index = int(row.get("chunk_index", 0) or 0)
                    content = str(row.get("content") or "")
                    embedding = self._normalize_vector(row.get("embedding", []) or [])
                    embedding_json = json.dumps(embedding, separators=(",", ":"))
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO rag_vec_chunks (
                            chunk_id, kb_id, doc_id, filename, file_type, chunk_index,
                            content, embedding_json, ingest_id, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (
                            chunk_id,
                            kb_id,
                            doc_id,
                            filename,
                            file_type,
                            chunk_index,
                            content,
                            embedding_json,
                            ingest_id,
                        ),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def delete_chunks_by_ids(self, *, kb_id: str, chunk_ids: List[str]) -> None:
        if not chunk_ids:
            return
        with self._lock, self._connect() as conn:
            placeholders = ",".join("?" for _ in chunk_ids)
            conn.execute(
                f"DELETE FROM rag_vec_chunks WHERE kb_id = ? AND chunk_id IN ({placeholders})",
                [kb_id, *chunk_ids],
            )
            conn.commit()

    def delete_stale_document_chunks(
        self,
        *,
        kb_id: str,
        doc_id: str,
        keep_chunk_ids: List[str],
    ) -> int:
        """Delete chunks in one document except current generation ids."""
        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            if keep_chunk_ids:
                placeholders = ",".join("?" for _ in keep_chunk_ids)
                params = [kb_id, doc_id, *keep_chunk_ids]
                cursor.execute(
                    f"""
                    DELETE FROM rag_vec_chunks
                    WHERE kb_id = ? AND doc_id = ? AND chunk_id NOT IN ({placeholders})
                    """,
                    params,
                )
            else:
                cursor.execute(
                    "DELETE FROM rag_vec_chunks WHERE kb_id = ? AND doc_id = ?",
                    (kb_id, doc_id),
                )
            deleted = int(cursor.rowcount or 0)
            conn.commit()
            return deleted

    def delete_document_chunks(self, *, kb_id: str, doc_id: str) -> int:
        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM rag_vec_chunks WHERE kb_id = ? AND doc_id = ?",
                (kb_id, doc_id),
            )
            deleted = int(cursor.rowcount or 0)
            conn.commit()
            return deleted

    def delete_kb_chunks(self, *, kb_id: str) -> int:
        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM rag_vec_chunks WHERE kb_id = ?", (kb_id,))
            deleted = int(cursor.rowcount or 0)
            conn.commit()
            return deleted

    def list_chunks(
        self,
        *,
        kb_id: str,
        doc_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, object]]:
        safe_limit = max(1, min(int(limit), 2000))
        with self._connect() as conn:
            if doc_id:
                rows = conn.execute(
                    """
                    SELECT chunk_id, kb_id, doc_id, filename, chunk_index, content
                    FROM rag_vec_chunks
                    WHERE kb_id = ? AND doc_id = ?
                    ORDER BY doc_id ASC, chunk_index ASC, chunk_id ASC
                    LIMIT ?
                    """,
                    (kb_id, doc_id, safe_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT chunk_id, kb_id, doc_id, filename, chunk_index, content
                    FROM rag_vec_chunks
                    WHERE kb_id = ?
                    ORDER BY doc_id ASC, chunk_index ASC, chunk_id ASC
                    LIMIT ?
                    """,
                    (kb_id, safe_limit),
                ).fetchall()

        items: List[Dict[str, object]] = []
        for row in rows:
            items.append(
                {
                    "id": str(row["chunk_id"]),
                    "kb_id": str(row["kb_id"]),
                    "doc_id": str(row["doc_id"]),
                    "filename": str(row["filename"]),
                    "chunk_index": int(row["chunk_index"]),
                    "content": str(row["content"] or ""),
                }
            )
        return items

    def search(
        self,
        *,
        kb_id: str,
        query_embedding: Sequence[float],
        top_k: int,
    ) -> List[Dict[str, object]]:
        query_vector = self._normalize_vector(query_embedding)
        if not query_vector:
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, kb_id, doc_id, filename, chunk_index, content, embedding_json
                FROM rag_vec_chunks
                WHERE kb_id = ?
                """,
                (kb_id,),
            ).fetchall()

        if not rows:
            return []

        ranked: List[Dict[str, object]] = []
        for row in rows:
            try:
                candidate_vector = self._normalize_vector(json.loads(row["embedding_json"] or "[]"))
            except Exception:
                continue
            score = self._cosine_similarity(query_vector, candidate_vector)
            ranked.append(
                {
                    "chunk_id": str(row["chunk_id"]),
                    "kb_id": str(row["kb_id"]),
                    "doc_id": str(row["doc_id"]),
                    "filename": str(row["filename"]),
                    "chunk_index": int(row["chunk_index"]),
                    "content": str(row["content"] or ""),
                    "score": float(score),
                }
            )

        ranked.sort(key=lambda item: float(item.get("score", 0.0) or 0.0), reverse=True)
        return ranked[: max(1, int(top_k))]
