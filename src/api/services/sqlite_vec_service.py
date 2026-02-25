"""
SQLite vector store service for RAG chunks.

This backend stores chunk metadata/content and embedding vectors in SQLite,
and uses sqlite-vec acceleration when available.
"""
from __future__ import annotations

import json
import logging
import math
import importlib
import sqlite3
import struct
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Sequence


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
        self._sqlite_vec_available = True
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        if self._sqlite_vec_available:
            self._try_load_sqlite_vec(conn)
        return conn

    def _try_load_sqlite_vec(self, conn: sqlite3.Connection) -> None:
        """Best-effort sqlite-vec extension load for SQL-side distance search."""
        if not self._sqlite_vec_available:
            return
        try:
            sqlite_vec = importlib.import_module("sqlite_vec")

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
        except Exception:
            self._sqlite_vec_available = False
            try:
                conn.enable_load_extension(False)
            except Exception:
                pass

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
                    embedding_blob BLOB,
                    embedding_dim INTEGER,
                    ingest_id TEXT DEFAULT '',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            existing_cols = {
                str(row["name"])
                for row in conn.execute("PRAGMA table_info(rag_vec_chunks)").fetchall()
            }
            if "embedding_blob" not in existing_cols:
                conn.execute("ALTER TABLE rag_vec_chunks ADD COLUMN embedding_blob BLOB")
            if "embedding_dim" not in existing_cols:
                conn.execute("ALTER TABLE rag_vec_chunks ADD COLUMN embedding_dim INTEGER")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_vec_kb ON rag_vec_chunks (kb_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_vec_kb_doc ON rag_vec_chunks (kb_id, doc_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rag_vec_kb_dim ON rag_vec_chunks (kb_id, embedding_dim)"
            )
            conn.commit()

    @staticmethod
    def _normalize_vector(vector: Sequence[float]) -> List[float]:
        return [float(item) for item in vector]

    @staticmethod
    def _pack_vector_float32(vector: Sequence[float]) -> bytes:
        if not vector:
            return b""
        normalized = [float(item) for item in vector]
        return struct.pack(f"<{len(normalized)}f", *normalized)

    @staticmethod
    def _unpack_vector_float32(blob: bytes, expected_dim: Optional[int] = None) -> List[float]:
        if not blob or len(blob) % 4 != 0:
            return []
        dim = len(blob) // 4
        if expected_dim is not None and dim != expected_dim:
            return []
        return list(struct.unpack(f"<{dim}f", blob))

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
        chunk_rows: List[Dict[str, Any]],
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
                    raw_embedding = row.get("embedding", []) or []
                    if not isinstance(raw_embedding, Sequence) or isinstance(raw_embedding, (str, bytes, bytearray)):
                        raw_embedding = []
                    embedding = self._normalize_vector(raw_embedding)
                    embedding_json = json.dumps(embedding, separators=(",", ":"))
                    embedding_blob = self._pack_vector_float32(embedding)
                    embedding_dim = len(embedding)
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO rag_vec_chunks (
                            chunk_id, kb_id, doc_id, filename, file_type, chunk_index,
                            content, embedding_json, embedding_blob, embedding_dim, ingest_id, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
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
                            embedding_blob,
                            embedding_dim,
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
    ) -> List[Dict[str, Any]]:
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

        items: List[Dict[str, Any]] = []
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

    def list_document_chunks_in_range(
        self,
        *,
        kb_id: str,
        doc_id: str,
        start_index: int,
        end_index: int,
        limit: int = 256,
    ) -> List[Dict[str, Any]]:
        """List chunks for one document within an inclusive chunk index range."""
        safe_start = max(0, int(start_index))
        safe_end = max(safe_start, int(end_index))
        safe_limit = max(1, min(int(limit), 2000))

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, kb_id, doc_id, filename, chunk_index, content
                FROM rag_vec_chunks
                WHERE kb_id = ? AND doc_id = ? AND chunk_index >= ? AND chunk_index <= ?
                ORDER BY chunk_index ASC
                LIMIT ?
                """,
                (kb_id, doc_id, safe_start, safe_end, safe_limit),
            ).fetchall()

        items: List[Dict[str, Any]] = []
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

    def _hydrate_missing_embedding_blobs(self, *, kb_id: str, max_rows: int = 2048) -> int:
        """
        Backfill binary float32 blobs for legacy rows that only have embedding_json.

        This keeps existing databases compatible while enabling faster SQL-side scoring.
        """
        safe_limit = max(1, int(max_rows))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, embedding_json
                FROM rag_vec_chunks
                WHERE kb_id = ? AND (embedding_blob IS NULL OR embedding_dim IS NULL)
                LIMIT ?
                """,
                (kb_id, safe_limit),
            ).fetchall()
            if not rows:
                return 0

            updates: List[tuple[bytes, int, str]] = []
            for row in rows:
                try:
                    vector = self._normalize_vector(json.loads(row["embedding_json"] or "[]"))
                except Exception:
                    continue
                if not vector:
                    continue
                updates.append((self._pack_vector_float32(vector), len(vector), str(row["chunk_id"])))

            if not updates:
                return 0

            conn.executemany(
                """
                UPDATE rag_vec_chunks
                SET embedding_blob = ?, embedding_dim = ?, updated_at = CURRENT_TIMESTAMP
                WHERE chunk_id = ?
                """,
                updates,
            )
            conn.commit()
            return len(updates)

    def _search_with_sqlite_vec(
        self,
        *,
        kb_id: str,
        query_vector: Sequence[float],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        if not self._sqlite_vec_available:
            return []

        query_dim = len(query_vector)
        if query_dim <= 0:
            return []
        query_blob = self._pack_vector_float32(query_vector)

        with self._connect() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT
                        chunk_id,
                        kb_id,
                        doc_id,
                        filename,
                        chunk_index,
                        content,
                        (1.0 - vec_distance_cosine(embedding_blob, ?)) AS score
                    FROM rag_vec_chunks
                    WHERE kb_id = ? AND embedding_dim = ? AND embedding_blob IS NOT NULL
                    ORDER BY score DESC
                    LIMIT ?
                    """,
                    (query_blob, kb_id, query_dim, top_k),
                ).fetchall()
            except sqlite3.OperationalError:
                self._sqlite_vec_available = False
                return []

        items: List[Dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "chunk_id": str(row["chunk_id"]),
                    "kb_id": str(row["kb_id"]),
                    "doc_id": str(row["doc_id"]),
                    "filename": str(row["filename"]),
                    "chunk_index": int(row["chunk_index"]),
                    "content": str(row["content"] or ""),
                    "score": float(row["score"] if row["score"] is not None else 0.0),
                }
            )
        return items

    def search(
        self,
        *,
        kb_id: str,
        query_embedding: Sequence[float],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        query_vector = self._normalize_vector(query_embedding)
        if not query_vector:
            return []
        safe_top_k = max(1, int(top_k))
        query_dim = len(query_vector)

        # Backfill legacy rows once so older DBs can use the optimized path.
        self._hydrate_missing_embedding_blobs(kb_id=kb_id)

        optimized = self._search_with_sqlite_vec(
            kb_id=kb_id,
            query_vector=query_vector,
            top_k=safe_top_k,
        )
        if optimized:
            return optimized

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    chunk_id,
                    kb_id,
                    doc_id,
                    filename,
                    chunk_index,
                    content,
                    embedding_json,
                    embedding_blob,
                    embedding_dim
                FROM rag_vec_chunks
                WHERE kb_id = ? AND (embedding_dim = ? OR embedding_dim IS NULL)
                """,
                (kb_id, query_dim),
            ).fetchall()

        if not rows:
            return []

        ranked: List[Dict[str, Any]] = []
        for row in rows:
            candidate_vector: List[float] = []
            blob = row["embedding_blob"]
            dim = row["embedding_dim"]
            if blob and isinstance(blob, (bytes, bytearray)):
                expected_dim = int(dim) if dim is not None else query_dim
                candidate_vector = self._unpack_vector_float32(bytes(blob), expected_dim=expected_dim)
            if not candidate_vector:
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
        return ranked[:safe_top_k]
