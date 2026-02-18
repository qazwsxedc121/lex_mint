"""
BM25 Service

Maintains a lightweight SQLite FTS5 index for lexical retrieval.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional


logger = logging.getLogger(__name__)


class Bm25Service:
    """Service for chunk-level BM25 indexing and retrieval."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from .rag_config_service import RagConfigService

            cfg = RagConfigService().config.storage
            db_path = str(getattr(cfg, "bm25_sqlite_path", "data/state/rag_bm25.sqlite3"))

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
                CREATE TABLE IF NOT EXISTS rag_bm25_chunks (
                    chunk_id TEXT PRIMARY KEY,
                    kb_id TEXT NOT NULL,
                    doc_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    tokenized TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS rag_bm25_fts
                USING fts5(
                    chunk_id,
                    tokenized,
                    tokenize='unicode61'
                )
                """
            )
            conn.commit()

    @staticmethod
    def _fallback_tokenize(text: str) -> List[str]:
        # Keep English words and single CJK chars as a safe fallback.
        pattern = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
        return pattern.findall(text.lower())

    @classmethod
    def tokenize_text(cls, text: str) -> List[str]:
        raw = (text or "").strip()
        if not raw:
            return []
        try:
            import jieba

            tokens = [tok.strip().lower() for tok in jieba.lcut_for_search(raw) if tok and tok.strip()]
        except Exception:
            tokens = cls._fallback_tokenize(raw)

        cleaned: List[str] = []
        for tok in tokens:
            if not tok:
                continue
            if re.fullmatch(r"[\W_]+", tok):
                continue
            cleaned.append(tok)
        return cleaned

    @classmethod
    def _to_tokenized_text(cls, text: str) -> str:
        return " ".join(cls.tokenize_text(text))

    @classmethod
    def _build_match_expression(cls, query: str) -> str:
        tokens = cls.tokenize_text(query)
        if not tokens:
            return ""
        escaped = [f"\"{tok.replace('\"', '\"\"')}\"" for tok in tokens]
        return " OR ".join(escaped)

    @classmethod
    def _significant_query_terms(cls, query: str) -> List[str]:
        tokens = cls.tokenize_text(query)
        if not tokens:
            return []

        seen = set()
        terms: List[str] = []
        for tok in tokens:
            if tok in seen:
                continue
            seen.add(tok)
            if len(tok) >= 2:
                terms.append(tok)

        if terms:
            return terms

        # Fallback for short-token queries so filtering does not hide all results.
        short_terms: List[str] = []
        for tok in tokens:
            if not tok or tok in short_terms:
                continue
            short_terms.append(tok)
        return short_terms

    @staticmethod
    def _calculate_term_coverage(query_terms: List[str], tokenized_text: str) -> tuple[float, int]:
        if not query_terms:
            return 1.0, 0
        if not tokenized_text:
            return 0.0, 0

        chunk_terms = {tok for tok in tokenized_text.split(" ") if tok}
        if not chunk_terms:
            return 0.0, 0

        matched_count = sum(1 for tok in query_terms if tok in chunk_terms)
        return matched_count / max(1, len(query_terms)), matched_count

    def upsert_document_chunks(
        self,
        *,
        kb_id: str,
        doc_id: str,
        filename: str,
        chunks: List[Dict[str, object]],
    ) -> None:
        """Upsert one document's chunk rows and refresh its FTS rows."""
        if not chunks:
            return

        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")
            try:
                current_ids: List[str] = []
                for row in chunks:
                    chunk_id = str(row.get("chunk_id") or "")
                    if not chunk_id:
                        continue
                    chunk_index = int(row.get("chunk_index", 0) or 0)
                    content = str(row.get("content") or "")
                    tokenized = self._to_tokenized_text(content)
                    current_ids.append(chunk_id)
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO rag_bm25_chunks (
                            chunk_id, kb_id, doc_id, filename, chunk_index, content, tokenized, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        (chunk_id, kb_id, doc_id, filename, chunk_index, content, tokenized),
                    )

                if current_ids:
                    placeholders = ",".join("?" for _ in current_ids)
                    params: List[object] = [kb_id, doc_id, *current_ids]
                    cursor.execute(
                        f"""
                        DELETE FROM rag_bm25_chunks
                        WHERE kb_id = ? AND doc_id = ? AND chunk_id NOT IN ({placeholders})
                        """,
                        params,
                    )
                else:
                    cursor.execute(
                        "DELETE FROM rag_bm25_chunks WHERE kb_id = ? AND doc_id = ?",
                        (kb_id, doc_id),
                    )

                doc_rows = cursor.execute(
                    """
                    SELECT chunk_id, tokenized
                    FROM rag_bm25_chunks
                    WHERE kb_id = ? AND doc_id = ?
                    """,
                    (kb_id, doc_id),
                ).fetchall()
                doc_chunk_ids = [str(item["chunk_id"]) for item in doc_rows]
                if doc_chunk_ids:
                    placeholders = ",".join("?" for _ in doc_chunk_ids)
                    cursor.execute(
                        f"DELETE FROM rag_bm25_fts WHERE chunk_id IN ({placeholders})",
                        doc_chunk_ids,
                    )
                for item in doc_rows:
                    cursor.execute(
                        "INSERT INTO rag_bm25_fts (chunk_id, tokenized) VALUES (?, ?)",
                        (str(item["chunk_id"]), str(item["tokenized"] or "")),
                    )

                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def delete_document_chunks(self, *, kb_id: str, doc_id: str) -> None:
        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT chunk_id FROM rag_bm25_chunks WHERE kb_id = ? AND doc_id = ?",
                (kb_id, doc_id),
            ).fetchall()
            chunk_ids = [str(item["chunk_id"]) for item in rows]
            cursor.execute("DELETE FROM rag_bm25_chunks WHERE kb_id = ? AND doc_id = ?", (kb_id, doc_id))
            if chunk_ids:
                placeholders = ",".join("?" for _ in chunk_ids)
                cursor.execute(f"DELETE FROM rag_bm25_fts WHERE chunk_id IN ({placeholders})", chunk_ids)
            conn.commit()

    def delete_kb_chunks(self, *, kb_id: str) -> None:
        with self._lock, self._connect() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT chunk_id FROM rag_bm25_chunks WHERE kb_id = ?",
                (kb_id,),
            ).fetchall()
            chunk_ids = [str(item["chunk_id"]) for item in rows]
            cursor.execute("DELETE FROM rag_bm25_chunks WHERE kb_id = ?", (kb_id,))
            if chunk_ids:
                placeholders = ",".join("?" for _ in chunk_ids)
                cursor.execute(f"DELETE FROM rag_bm25_fts WHERE chunk_id IN ({placeholders})", chunk_ids)
            conn.commit()

    def search(
        self,
        *,
        kb_id: str,
        query: str,
        top_k: int,
        min_term_coverage: float = 0.0,
    ) -> List[Dict[str, object]]:
        match_expr = self._build_match_expression(query)
        if not match_expr:
            return []

        safe_top_k = max(1, int(top_k))
        safe_min_term_coverage = max(0.0, min(1.0, float(min_term_coverage or 0.0)))
        fetch_k = safe_top_k
        if safe_min_term_coverage > 0:
            fetch_k = min(max(safe_top_k * 5, safe_top_k), 1000)

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    c.chunk_id,
                    c.kb_id,
                    c.doc_id,
                    c.filename,
                    c.chunk_index,
                    c.content,
                    c.tokenized,
                    bm25(rag_bm25_fts) AS bm25_score
                FROM rag_bm25_fts
                JOIN rag_bm25_chunks c ON c.chunk_id = rag_bm25_fts.chunk_id
                WHERE rag_bm25_fts.tokenized MATCH ? AND c.kb_id = ?
                ORDER BY bm25_score ASC
                LIMIT ?
                """,
                (match_expr, kb_id, fetch_k),
            ).fetchall()

        if not rows:
            return []

        filtered_rows: List[tuple[sqlite3.Row, float, int]] = []
        if safe_min_term_coverage > 0:
            query_terms = self._significant_query_terms(query)
            for row in rows:
                coverage, matched_count = self._calculate_term_coverage(
                    query_terms,
                    str(row["tokenized"] or ""),
                )
                if coverage + 1e-12 < safe_min_term_coverage:
                    continue
                filtered_rows.append((row, coverage, matched_count))
                if len(filtered_rows) >= safe_top_k:
                    break
        else:
            filtered_rows = [(row, 1.0, 0) for row in rows[:safe_top_k]]

        if not filtered_rows:
            return []

        raw_scores = [float(row["bm25_score"]) for row, _, _ in filtered_rows]
        min_score = min(raw_scores)
        max_score = max(raw_scores)
        if max_score - min_score <= 1e-12:
            normalized = [1.0 for _ in raw_scores]
        else:
            normalized = [(max_score - val) / (max_score - min_score) for val in raw_scores]

        items: List[Dict[str, object]] = []
        for index, (row, coverage, matched_count) in enumerate(filtered_rows):
            items.append(
                {
                    "chunk_id": str(row["chunk_id"]),
                    "kb_id": str(row["kb_id"]),
                    "doc_id": str(row["doc_id"]),
                    "filename": str(row["filename"]),
                    "chunk_index": int(row["chunk_index"]),
                    "content": str(row["content"]),
                    "score": float(normalized[index]),
                    "bm25_score": float(row["bm25_score"]),
                    "term_coverage": float(coverage),
                    "matched_query_terms": int(matched_count),
                }
            )
        return items
