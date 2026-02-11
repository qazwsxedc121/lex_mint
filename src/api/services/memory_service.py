"""Memory service backed by ChromaDB.

Provides CRUD, retrieval and lightweight extraction utilities for global/assistant memory.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .embedding_service import EmbeddingService
from .memory_config_service import MemoryConfigService
from .rag_config_service import RagConfigService

logger = logging.getLogger(__name__)


@dataclass
class MemoryResult:
    id: str
    content: str
    score: Optional[float]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "content": self.content,
            "score": self.score,
        }
        data.update(self.metadata)
        return data


class MemoryService:
    """Service for long-term memory operations."""

    VALID_SCOPES = {"global", "assistant"}
    VALID_LAYERS = {"identity", "preference", "context", "experience", "activity"}

    IDENTITY_KEYWORDS = (
        "我是",
        "我叫",
        "我的名字",
        "我在",
        "我住",
        "我的职业",
        "我工作",
        "i am",
        "i'm",
        "my name",
        "i work",
        "i live",
    )

    PREFERENCE_KEYWORDS = (
        "我喜欢",
        "我不喜欢",
        "请用",
        "请不要",
        "以后",
        "回答时",
        "输出",
        "尽量",
        "优先",
        "偏好",
        "prefer",
        "please",
        "use ",
        "respond",
        "answer in",
        "call me",
        "don't",
    )

    GLOBAL_HINTS = (
        "所有对话",
        "所有助手",
        "全局",
        "一直",
        "always",
        "in every chat",
        "for all",
    )

    def __init__(
        self,
        memory_config_service: Optional[MemoryConfigService] = None,
        rag_config_service: Optional[RagConfigService] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self.memory_config_service = memory_config_service or MemoryConfigService()
        self.rag_config_service = rag_config_service or RagConfigService()
        self.embedding_service = embedding_service or EmbeddingService()

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "")).strip()

    def _resolve_profile_id(self, profile_id: Optional[str]) -> str:
        if profile_id:
            return profile_id
        return self.memory_config_service.config.profile_id

    def _resolve_persist_dir(self) -> Path:
        persist_dir = Path(self.rag_config_service.config.storage.persist_directory)
        if not persist_dir.is_absolute():
            persist_dir = Path(__file__).parent.parent.parent.parent / persist_dir
        persist_dir.mkdir(parents=True, exist_ok=True)
        return persist_dir

    def _get_vectorstore(self):
        from langchain_chroma import Chroma

        cfg = self.memory_config_service.config
        persist_dir = self._resolve_persist_dir()
        embedding_fn = self.embedding_service.get_embedding_function()

        return Chroma(
            collection_name=cfg.collection_name,
            embedding_function=embedding_fn,
            persist_directory=str(persist_dir),
            collection_metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _build_where(filters: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        filters = [flt for flt in filters if flt]
        if not filters:
            return None
        if len(filters) == 1:
            return filters[0]
        return {"$and": list(filters)}

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _validate_scope_layer(self, scope: str, layer: str, assistant_id: Optional[str] = None) -> None:
        if scope not in self.VALID_SCOPES:
            raise ValueError(f"Invalid scope: {scope}")
        if scope == "assistant" and not assistant_id:
            raise ValueError("assistant_id is required when scope='assistant'")
        if layer not in self.VALID_LAYERS:
            raise ValueError(f"Invalid layer: {layer}")

    def _content_hash(
        self,
        profile_id: str,
        scope: str,
        layer: str,
        content: str,
        assistant_id: Optional[str] = None,
    ) -> str:
        payload = "|".join(
            [
                profile_id,
                scope,
                assistant_id or "",
                layer,
                self._clean_text(content).lower(),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _metadata_to_result(
        memory_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]],
        score: Optional[float] = None,
    ) -> MemoryResult:
        meta = metadata or {}
        return MemoryResult(
            id=memory_id,
            content=content,
            score=score,
            metadata={
                "profile_id": meta.get("profile_id"),
                "scope": meta.get("scope"),
                "assistant_id": meta.get("assistant_id"),
                "layer": meta.get("layer"),
                "confidence": meta.get("confidence"),
                "importance": meta.get("importance"),
                "source_session_id": meta.get("source_session_id"),
                "source_message_id": meta.get("source_message_id"),
                "created_at": meta.get("created_at"),
                "updated_at": meta.get("updated_at"),
                "last_hit_at": meta.get("last_hit_at"),
                "hit_count": meta.get("hit_count", 0),
                "is_active": meta.get("is_active", True),
                "pinned": meta.get("pinned", False),
                "hash": meta.get("hash"),
            },
        )

    def list_memories(
        self,
        *,
        profile_id: Optional[str] = None,
        scope: Optional[str] = None,
        assistant_id: Optional[str] = None,
        layer: Optional[str] = None,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        resolved_profile = self._resolve_profile_id(profile_id)
        cfg = self.memory_config_service.config

        filters: List[Dict[str, Any]] = [{"profile_id": resolved_profile}]
        if scope:
            if scope not in self.VALID_SCOPES:
                raise ValueError(f"Invalid scope: {scope}")
            filters.append({"scope": scope})
        if assistant_id:
            filters.append({"assistant_id": assistant_id})
        if layer:
            if layer not in self.VALID_LAYERS:
                raise ValueError(f"Invalid layer: {layer}")
            filters.append({"layer": layer})
        if not include_inactive:
            filters.append({"is_active": True})

        where = self._build_where(filters)
        vectorstore = self._get_vectorstore()

        response = vectorstore._collection.get(
            where=where,
            limit=max(1, min(limit, 500)),
            include=["documents", "metadatas"],
        )

        ids = response.get("ids") or []
        docs = response.get("documents") or []
        metas = response.get("metadatas") or []

        results: List[Dict[str, Any]] = []
        for idx, memory_id in enumerate(ids):
            content = docs[idx] if idx < len(docs) else ""
            metadata = metas[idx] if idx < len(metas) else {}
            item = self._metadata_to_result(memory_id, content, metadata).to_dict()
            results.append(item)

        # Keep pinned items first, then latest update first.
        results.sort(
            key=lambda x: (
                0 if x.get("pinned") else 1,
                x.get("updated_at") or "",
            ),
            reverse=False,
        )
        return results

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        vectorstore = self._get_vectorstore()
        response = vectorstore._collection.get(ids=[memory_id], include=["documents", "metadatas"])
        ids = response.get("ids") or []
        if not ids:
            return None

        docs = response.get("documents") or []
        metas = response.get("metadatas") or []
        return self._metadata_to_result(
            ids[0],
            docs[0] if docs else "",
            metas[0] if metas else {},
        ).to_dict()

    def upsert_memory(
        self,
        *,
        content: str,
        scope: str,
        layer: str,
        assistant_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        confidence: float = 0.8,
        importance: float = 0.6,
        source_session_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        pinned: bool = False,
        is_active: bool = True,
        memory_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        resolved_profile = self._resolve_profile_id(profile_id)
        clean_content = self._clean_text(content)
        if not clean_content:
            raise ValueError("content cannot be empty")

        self._validate_scope_layer(scope, layer, assistant_id)

        content_hash = self._content_hash(
            resolved_profile,
            scope=scope,
            layer=layer,
            content=clean_content,
            assistant_id=assistant_id,
        )

        now = self._now_iso()
        vectorstore = self._get_vectorstore()
        collection = vectorstore._collection

        existing_id = memory_id
        if not existing_id:
            existing = collection.get(
                where=self._build_where([
                    {"profile_id": resolved_profile},
                    {"hash": content_hash},
                ]),
                limit=1,
                include=["metadatas"],
            )
            existing_ids = existing.get("ids") or []
            if existing_ids:
                existing_id = existing_ids[0]

        if existing_id:
            current = collection.get(ids=[existing_id], include=["documents", "metadatas"])
            current_ids = current.get("ids") or []
            if current_ids:
                current_meta = (current.get("metadatas") or [{}])[0] or {}
                metadata = {
                    **current_meta,
                    "id": existing_id,
                    "profile_id": resolved_profile,
                    "scope": scope,
                    "assistant_id": assistant_id,
                    "layer": layer,
                    "confidence": float(confidence),
                    "importance": float(importance),
                    "source_session_id": source_session_id or current_meta.get("source_session_id"),
                    "source_message_id": source_message_id or current_meta.get("source_message_id"),
                    "hash": content_hash,
                    "updated_at": now,
                    "last_hit_at": current_meta.get("last_hit_at"),
                    "hit_count": int(current_meta.get("hit_count", 0) or 0),
                    "is_active": bool(is_active),
                    "pinned": bool(pinned or current_meta.get("pinned", False)),
                    "created_at": current_meta.get("created_at", now),
                }
                collection.upsert(ids=[existing_id], documents=[clean_content], metadatas=[metadata])
                return self.get_memory(existing_id) or {}

        final_id = memory_id or f"mem_{uuid.uuid4().hex}"
        metadata = {
            "id": final_id,
            "profile_id": resolved_profile,
            "scope": scope,
            "assistant_id": assistant_id,
            "layer": layer,
            "confidence": float(confidence),
            "importance": float(importance),
            "source_session_id": source_session_id,
            "source_message_id": source_message_id,
            "hash": content_hash,
            "created_at": now,
            "updated_at": now,
            "last_hit_at": None,
            "hit_count": 0,
            "is_active": bool(is_active),
            "pinned": bool(pinned),
        }

        vectorstore.add_texts(texts=[clean_content], ids=[final_id], metadatas=[metadata])
        return self.get_memory(final_id) or {}

    def update_memory(
        self,
        memory_id: str,
        *,
        content: Optional[str] = None,
        scope: Optional[str] = None,
        layer: Optional[str] = None,
        assistant_id: Optional[str] = None,
        confidence: Optional[float] = None,
        importance: Optional[float] = None,
        pinned: Optional[bool] = None,
        is_active: Optional[bool] = None,
    ) -> Dict[str, Any]:
        vectorstore = self._get_vectorstore()
        collection = vectorstore._collection
        current = collection.get(ids=[memory_id], include=["documents", "metadatas"])
        ids = current.get("ids") or []
        if not ids:
            raise FileNotFoundError(f"Memory {memory_id} not found")

        current_doc = (current.get("documents") or [""])[0]
        current_meta = (current.get("metadatas") or [{}])[0] or {}

        next_scope = scope or current_meta.get("scope") or "global"
        next_layer = layer or current_meta.get("layer") or "preference"
        next_assistant_id = assistant_id if assistant_id is not None else current_meta.get("assistant_id")
        next_content = self._clean_text(content) if content is not None else current_doc
        if not next_content:
            raise ValueError("content cannot be empty")

        self._validate_scope_layer(next_scope, next_layer, next_assistant_id)

        profile_id = current_meta.get("profile_id") or self._resolve_profile_id(None)
        next_hash = self._content_hash(
            profile_id=profile_id,
            scope=next_scope,
            layer=next_layer,
            assistant_id=next_assistant_id,
            content=next_content,
        )

        metadata = {
            **current_meta,
            "id": memory_id,
            "scope": next_scope,
            "layer": next_layer,
            "assistant_id": next_assistant_id,
            "confidence": float(confidence) if confidence is not None else self._safe_float(current_meta.get("confidence"), 0.8),
            "importance": float(importance) if importance is not None else self._safe_float(current_meta.get("importance"), 0.6),
            "pinned": bool(pinned) if pinned is not None else bool(current_meta.get("pinned", False)),
            "is_active": bool(is_active) if is_active is not None else bool(current_meta.get("is_active", True)),
            "hash": next_hash,
            "updated_at": self._now_iso(),
        }

        collection.upsert(ids=[memory_id], documents=[next_content], metadatas=[metadata])
        return self.get_memory(memory_id) or {}

    def delete_memory(self, memory_id: str) -> bool:
        vectorstore = self._get_vectorstore()
        vectorstore._collection.delete(ids=[memory_id])
        return True

    def _search_scope(
        self,
        *,
        query: str,
        profile_id: str,
        scope: str,
        assistant_id: Optional[str],
        top_k: int,
        score_threshold: float,
        layer: Optional[str] = None,
    ) -> List[MemoryResult]:
        filters: List[Dict[str, Any]] = [
            {"profile_id": profile_id},
            {"scope": scope},
            {"is_active": True},
        ]
        if assistant_id:
            filters.append({"assistant_id": assistant_id})
        if layer:
            filters.append({"layer": layer})

        where = self._build_where(filters)
        vectorstore = self._get_vectorstore()
        docs_and_scores = vectorstore.similarity_search_with_relevance_scores(
            query,
            k=max(1, top_k),
            filter=where,
        )

        results: List[MemoryResult] = []
        for doc, score in docs_and_scores:
            if score < score_threshold:
                continue
            memory_id = (doc.metadata or {}).get("id")
            # Chroma keeps the document id in metadata only if injected manually.
            if not memory_id:
                memory_id = (doc.metadata or {}).get("memory_id")
            if not memory_id:
                # Fall back to hash to keep source traceable if id is unavailable.
                memory_id = (doc.metadata or {}).get("hash", "")

            item = self._metadata_to_result(
                memory_id=memory_id,
                content=doc.page_content,
                metadata=doc.metadata,
                score=score,
            )
            results.append(item)

        return results

    def _refresh_ids_from_collection(self, results: List[MemoryResult], profile_id: str) -> List[MemoryResult]:
        """Map hash-based fallback IDs back to true Chroma IDs when possible."""
        unresolved = [item for item in results if not item.id or item.id == item.metadata.get("hash")]
        if not unresolved:
            return results

        vectorstore = self._get_vectorstore()
        for item in unresolved:
            content_hash = item.metadata.get("hash")
            if not content_hash:
                continue
            response = vectorstore._collection.get(
                where=self._build_where([
                    {"profile_id": profile_id},
                    {"hash": content_hash},
                ]),
                limit=1,
                include=["metadatas"],
            )
            ids = response.get("ids") or []
            if ids:
                item.id = ids[0]
        return results

    def search_memories(
        self,
        *,
        query: str,
        profile_id: Optional[str] = None,
        scope: str,
        assistant_id: Optional[str] = None,
        layer: Optional[str] = None,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        clean_query = self._clean_text(query)
        if not clean_query:
            return []

        if scope not in self.VALID_SCOPES:
            raise ValueError(f"Invalid scope: {scope}")
        if scope == "assistant" and not assistant_id:
            raise ValueError("assistant_id is required when scope='assistant'")

        if layer and layer not in self.VALID_LAYERS:
            raise ValueError(f"Invalid layer: {layer}")

        cfg = self.memory_config_service.config
        resolved_profile = self._resolve_profile_id(profile_id)
        effective_top_k = top_k if top_k is not None else cfg.retrieval.top_k
        effective_threshold = score_threshold if score_threshold is not None else cfg.retrieval.score_threshold

        items = self._search_scope(
            query=clean_query,
            profile_id=resolved_profile,
            scope=scope,
            assistant_id=assistant_id,
            top_k=effective_top_k,
            score_threshold=effective_threshold,
            layer=layer,
        )
        items = self._refresh_ids_from_collection(items, resolved_profile)

        items.sort(key=lambda x: x.score or 0.0, reverse=True)
        return [item.to_dict() for item in items]

    def search_memories_for_scopes(
        self,
        *,
        query: str,
        assistant_id: Optional[str],
        profile_id: Optional[str] = None,
        include_global: bool = True,
        include_assistant: bool = True,
        layer: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clean_query = self._clean_text(query)
        if not clean_query:
            return []

        cfg = self.memory_config_service.config
        if not cfg.enabled:
            return []

        resolved_profile = self._resolve_profile_id(profile_id)
        effective_limit = limit if limit is not None else cfg.retrieval.max_injected_items

        all_results: List[MemoryResult] = []
        if include_global and cfg.scopes.global_enabled:
            all_results.extend(
                self._search_scope(
                    query=clean_query,
                    profile_id=resolved_profile,
                    scope="global",
                    assistant_id=None,
                    top_k=cfg.retrieval.top_k,
                    score_threshold=cfg.retrieval.score_threshold,
                    layer=layer,
                )
            )

        if (
            include_assistant
            and cfg.scopes.assistant_enabled
            and assistant_id
        ):
            all_results.extend(
                self._search_scope(
                    query=clean_query,
                    profile_id=resolved_profile,
                    scope="assistant",
                    assistant_id=assistant_id,
                    top_k=cfg.retrieval.top_k,
                    score_threshold=cfg.retrieval.score_threshold,
                    layer=layer,
                )
            )

        all_results = self._refresh_ids_from_collection(all_results, resolved_profile)

        dedup: Dict[str, MemoryResult] = {}
        for item in all_results:
            key = item.id or item.metadata.get("hash")
            if not key:
                continue
            old = dedup.get(key)
            if old is None or (item.score or 0.0) > (old.score or 0.0):
                dedup[key] = item

        merged = list(dedup.values())
        merged.sort(key=lambda x: x.score or 0.0, reverse=True)
        return [item.to_dict() for item in merged[: max(1, effective_limit)]]

    def build_memory_context(
        self,
        *,
        query: str,
        assistant_id: Optional[str],
        profile_id: Optional[str] = None,
        include_global: bool = True,
        include_assistant: bool = True,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        cfg = self.memory_config_service.config
        if not cfg.enabled:
            return "", []

        results = self.search_memories_for_scopes(
            query=query,
            assistant_id=assistant_id,
            profile_id=profile_id,
            include_global=include_global,
            include_assistant=include_assistant,
            limit=cfg.retrieval.max_injected_items,
        )
        if not results:
            return "", []

        lines = [
            "User memory context (long-term identity and preferences):",
            "Use when relevant. Do not expose memory metadata in your answer.",
        ]

        sources: List[Dict[str, Any]] = []
        for idx, item in enumerate(results, start=1):
            content = self._clean_text(item.get("content", ""))
            if len(content) > cfg.retrieval.max_item_length:
                content = f"{content[:cfg.retrieval.max_item_length]}..."

            scope = item.get("scope") or "global"
            layer = item.get("layer") or "preference"
            score = self._safe_float(item.get("score"), 0.0)
            lines.append(f"[{idx}] ({scope}/{layer}, score={score:.2f}) {content}")

            sources.append(
                {
                    "type": "memory",
                    "id": item.get("id"),
                    "scope": scope,
                    "layer": layer,
                    "score": score,
                    "content": content,
                }
            )

        return "\n".join(lines), sources

    def _split_sentences(self, text: str) -> List[str]:
        chunks = re.split(r"[\n\r。！？!?]+|(?<=[.])\s+", text)
        return [self._clean_text(chunk) for chunk in chunks if self._clean_text(chunk)]

    def _is_identity_sentence(self, sentence: str) -> bool:
        lower = sentence.lower()
        return any(keyword in sentence for keyword in self.IDENTITY_KEYWORDS) or any(
            keyword in lower for keyword in self.IDENTITY_KEYWORDS
        )

    def _is_preference_sentence(self, sentence: str) -> bool:
        lower = sentence.lower()
        return any(keyword in sentence for keyword in self.PREFERENCE_KEYWORDS) or any(
            keyword in lower for keyword in self.PREFERENCE_KEYWORDS
        )

    def _is_global_hint(self, sentence: str) -> bool:
        lower = sentence.lower()
        return any(keyword in sentence for keyword in self.GLOBAL_HINTS) or any(
            keyword in lower for keyword in self.GLOBAL_HINTS
        )

    def extract_memory_candidates(self, text: str) -> List[Dict[str, Any]]:
        cfg = self.memory_config_service.config
        sentences = self._split_sentences(text)
        if not sentences:
            return []

        max_items = max(1, cfg.extraction.max_items_per_turn)
        min_len = max(1, cfg.extraction.min_text_length)
        enabled_layers = set(cfg.enabled_layers or [])

        candidates: List[Dict[str, Any]] = []
        seen = set()

        for sentence in sentences:
            if len(sentence) < min_len:
                continue

            layer = None
            confidence = 0.0
            importance = 0.0

            if "identity" in enabled_layers and self._is_identity_sentence(sentence):
                layer = "identity"
                confidence = 0.9
                importance = 0.75
            elif "preference" in enabled_layers and self._is_preference_sentence(sentence):
                layer = "preference"
                confidence = 0.82
                importance = 0.68

            if not layer:
                continue

            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)

            candidates.append(
                {
                    "content": sentence,
                    "layer": layer,
                    "confidence": confidence,
                    "importance": importance,
                    "prefer_global": self._is_global_hint(sentence),
                }
            )
            if len(candidates) >= max_items:
                break

        return candidates

    async def extract_and_persist_from_turn(
        self,
        *,
        user_message: str,
        assistant_message: str,
        assistant_id: Optional[str],
        profile_id: Optional[str] = None,
        source_session_id: Optional[str] = None,
        source_message_id: Optional[str] = None,
        assistant_memory_enabled: bool = True,
    ) -> List[Dict[str, Any]]:
        cfg = self.memory_config_service.config
        if not cfg.enabled or not cfg.extraction.enabled:
            return []

        candidates = self.extract_memory_candidates(user_message)
        if not candidates:
            return []

        stored: List[Dict[str, Any]] = []
        for candidate in candidates:
            layer = candidate["layer"]
            scope = "global"

            if layer != "identity" and assistant_memory_enabled and assistant_id and cfg.scopes.assistant_enabled:
                scope = "assistant"

            if candidate.get("prefer_global"):
                scope = "global"

            if scope == "global" and not cfg.scopes.global_enabled:
                if assistant_memory_enabled and assistant_id and cfg.scopes.assistant_enabled:
                    scope = "assistant"
                else:
                    continue

            if scope == "assistant" and (not assistant_id or not assistant_memory_enabled or not cfg.scopes.assistant_enabled):
                if cfg.scopes.global_enabled:
                    scope = "global"
                else:
                    continue

            try:
                item = await asyncio.to_thread(
                    self.upsert_memory,
                    content=candidate["content"],
                    scope=scope,
                    layer=layer,
                    assistant_id=assistant_id if scope == "assistant" else None,
                    profile_id=profile_id,
                    confidence=candidate["confidence"],
                    importance=candidate["importance"],
                    source_session_id=source_session_id,
                    source_message_id=source_message_id,
                    pinned=False,
                    is_active=True,
                )
                if item:
                    stored.append(item)
            except Exception as e:
                logger.warning("Failed to upsert memory item: %s", e)

        if stored:
            logger.info("Stored %d memory item(s) from latest turn", len(stored))
        return stored
