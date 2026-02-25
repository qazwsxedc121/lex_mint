"""
Knowledge Base configuration management service

Handles loading, saving, and managing knowledge base configurations and documents.
"""
import asyncio
import json
import os
import yaml
import aiofiles
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from ..models.knowledge_base import (
    KnowledgeBase,
    KnowledgeBaseDocument,
    KnowledgeBasesConfig,
)

from ..paths import data_state_dir, repo_root

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """Knowledge base configuration management service"""
    # Protect YAML read/write in-process so concurrent uploads do not corrupt config on Windows.
    _config_lock = asyncio.Lock()
    # Protect load-modify-save sequences so concurrent writers do not lose updates.
    _mutation_lock = asyncio.Lock()
    _io_retry_attempts = 8
    _io_retry_delay_seconds = 0.1
    _doc_events_compact_threshold = 2000
    # Shared cache by config path so short-lived service instances can reuse parsed YAML.
    _config_cache: Dict[str, KnowledgeBasesConfig] = {}
    _config_cache_mtime_ns: Dict[str, int] = {}
    # Shared in-memory document store backed by snapshot/events text files.
    _docs_lock = asyncio.Lock()
    _docs_loaded: Dict[str, bool] = {}
    _docs_cache: Dict[str, Dict[str, KnowledgeBaseDocument]] = {}
    _docs_snapshot_mtime_ns: Dict[str, int] = {}
    _docs_events_mtime_ns: Dict[str, int] = {}
    _docs_event_count: Dict[str, int] = {}

    def __init__(self, config_path: Optional[Path] = None, storage_dir: Optional[Path] = None):
        if config_path is None:
            config_path = data_state_dir() / "knowledge_bases_config.yaml"
        if storage_dir is None:
            preferred = repo_root() / "data" / "knowledge_bases"
            legacy = repo_root() / "knowledge_bases"
            if preferred.exists():
                storage_dir = preferred
            elif legacy.exists():
                storage_dir = legacy
            else:
                storage_dir = preferred

        self.config_path = config_path
        self.storage_dir = storage_dir
        state_dir = self.config_path.parent
        self.docs_snapshot_path = state_dir / "knowledge_base_documents.snapshot.jsonl"
        self.docs_events_path = state_dir / "knowledge_base_documents.events.jsonl"
        self._ensure_config_exists()
        self._ensure_doc_store_files_exist()

    def _ensure_config_exists(self):
        """Ensure configuration file exists, create default if not"""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            default_config = {'knowledge_bases': [], 'documents': []}
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(default_config, f, allow_unicode=True, sort_keys=False)

    def _cache_key(self) -> str:
        try:
            return str(self.config_path.resolve()).lower()
        except Exception:
            return str(self.config_path).lower()

    def _doc_store_key(self) -> str:
        try:
            return str(self.docs_snapshot_path.resolve()).lower()
        except Exception:
            return str(self.docs_snapshot_path).lower()

    @staticmethod
    def _doc_cache_key(kb_id: str, doc_id: str) -> str:
        return f"{kb_id}::{doc_id}"

    def _ensure_doc_store_files_exist(self) -> None:
        self.docs_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.docs_snapshot_path.exists():
            self.docs_snapshot_path.write_text("", encoding="utf-8")
        if not self.docs_events_path.exists():
            self.docs_events_path.write_text("", encoding="utf-8")

    async def _write_docs_snapshot(self, docs_map: Dict[str, KnowledgeBaseDocument]) -> None:
        temp_path = self.docs_snapshot_path.with_suffix(".jsonl.tmp")
        lines: List[str] = []
        for item in docs_map.values():
            payload = item.model_dump(mode="json")
            lines.append(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        content = ("\n".join(lines) + "\n") if lines else ""
        async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
            await f.write(content)
        os.replace(str(temp_path), str(self.docs_snapshot_path))

    async def _append_doc_events(self, events: List[Dict[str, object]]) -> None:
        if not events:
            return
        lines = [
            json.dumps(event, ensure_ascii=False, separators=(",", ":"))
            for event in events
        ]
        payload = "\n".join(lines) + "\n"
        async with aiofiles.open(self.docs_events_path, "a", encoding="utf-8") as f:
            await f.write(payload)

    async def _compact_doc_events_if_needed(self, store_key: str) -> None:
        event_count = int(self._docs_event_count.get(store_key, 0) or 0)
        if event_count < self._doc_events_compact_threshold:
            return
        docs_map = self._docs_cache.get(store_key, {})
        await self._write_docs_snapshot(docs_map)
        async with aiofiles.open(self.docs_events_path, "w", encoding="utf-8") as f:
            await f.write("")
        self._docs_event_count[store_key] = 0
        self._docs_snapshot_mtime_ns[store_key] = int(self.docs_snapshot_path.stat().st_mtime_ns)
        self._docs_events_mtime_ns[store_key] = int(self.docs_events_path.stat().st_mtime_ns)

    async def _migrate_yaml_documents_if_needed(self) -> None:
        if self.docs_snapshot_path.exists() and self.docs_snapshot_path.stat().st_size > 0:
            return
        if self.docs_events_path.exists() and self.docs_events_path.stat().st_size > 0:
            return

        config = await self.load_config()
        if not config.documents:
            return

        docs_map: Dict[str, KnowledgeBaseDocument] = {}
        for doc in config.documents:
            docs_map[self._doc_cache_key(doc.kb_id, doc.id)] = doc

        await self._write_docs_snapshot(docs_map)
        async with aiofiles.open(self.docs_events_path, "w", encoding="utf-8") as f:
            await f.write("")

        # Keep YAML focused on KB definitions after migration.
        config.documents = []
        await self.save_config(config)

    async def _ensure_docs_cache_loaded(self) -> None:
        store_key = self._doc_store_key()
        async with self._docs_lock:
            await self._migrate_yaml_documents_if_needed()

            snapshot_mtime = int(self.docs_snapshot_path.stat().st_mtime_ns)
            events_mtime = int(self.docs_events_path.stat().st_mtime_ns)
            already_loaded = bool(self._docs_loaded.get(store_key, False))
            if (
                already_loaded
                and self._docs_snapshot_mtime_ns.get(store_key) == snapshot_mtime
                and self._docs_events_mtime_ns.get(store_key) == events_mtime
            ):
                return

            docs_map: Dict[str, KnowledgeBaseDocument] = {}
            event_count = 0

            async with aiofiles.open(self.docs_snapshot_path, "r", encoding="utf-8") as f:
                snapshot_raw = await f.read()
            for raw in snapshot_raw.splitlines():
                line = raw.strip()
                if not line:
                    continue
                payload = json.loads(line)
                doc = KnowledgeBaseDocument(**payload)
                docs_map[self._doc_cache_key(doc.kb_id, doc.id)] = doc

            async with aiofiles.open(self.docs_events_path, "r", encoding="utf-8") as f:
                events_raw = await f.read()
            for raw in events_raw.splitlines():
                line = raw.strip()
                if not line:
                    continue
                event_count += 1
                payload = json.loads(line)
                op = str(payload.get("op") or "").strip().lower()
                if op == "upsert":
                    doc_payload = payload.get("doc") or {}
                    doc = KnowledgeBaseDocument(**doc_payload)
                    docs_map[self._doc_cache_key(doc.kb_id, doc.id)] = doc
                    continue
                if op == "delete":
                    kb_id = str(payload.get("kb_id") or "").strip()
                    doc_id = str(payload.get("doc_id") or "").strip()
                    if kb_id and doc_id:
                        docs_map.pop(self._doc_cache_key(kb_id, doc_id), None)
                    continue
                if op == "delete_kb":
                    kb_id = str(payload.get("kb_id") or "").strip()
                    if kb_id:
                        to_delete = [key for key, doc in docs_map.items() if doc.kb_id == kb_id]
                        for key in to_delete:
                            docs_map.pop(key, None)

            self._docs_cache[store_key] = docs_map
            self._docs_event_count[store_key] = event_count
            self._docs_loaded[store_key] = True
            self._docs_snapshot_mtime_ns[store_key] = snapshot_mtime
            self._docs_events_mtime_ns[store_key] = events_mtime

    async def load_config(self) -> KnowledgeBasesConfig:
        """Load configuration file"""
        last_error: Exception | None = None
        for attempt in range(self._io_retry_attempts):
            try:
                async with self._config_lock:
                    cache_key = self._cache_key()
                    mtime_ns = int(self.config_path.stat().st_mtime_ns)
                    cached = self._config_cache.get(cache_key)
                    cached_mtime = self._config_cache_mtime_ns.get(cache_key)
                    if cached is not None and cached_mtime == mtime_ns:
                        return cached.model_copy(deep=True)

                    async with aiofiles.open(self.config_path, 'r', encoding='utf-8') as f:
                        content = await f.read()
                data = yaml.safe_load(content) or {}
                config = KnowledgeBasesConfig(**data)
                async with self._config_lock:
                    self._config_cache[cache_key] = config.model_copy(deep=True)
                    self._config_cache_mtime_ns[cache_key] = mtime_ns
                return config.model_copy(deep=True)
            except (OSError, yaml.YAMLError) as e:
                last_error = e
                if attempt + 1 >= self._io_retry_attempts:
                    break
                await asyncio.sleep(self._io_retry_delay_seconds * (attempt + 1))
        raise RuntimeError(f"Failed to load knowledge base config: {last_error}") from last_error

    async def save_config(self, config: KnowledgeBasesConfig):
        """Save configuration file with atomic replace and retry."""
        content = yaml.safe_dump(
            config.model_dump(mode='json'),
            allow_unicode=True,
            sort_keys=False
        )
        temp_path = self.config_path.with_suffix('.yaml.tmp')
        last_error: Exception | None = None
        for attempt in range(self._io_retry_attempts):
            try:
                async with self._config_lock:
                    async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
                        await f.write(content)
                    os.replace(str(temp_path), str(self.config_path))
                    cache_key = self._cache_key()
                    self._config_cache[cache_key] = config.model_copy(deep=True)
                    self._config_cache_mtime_ns[cache_key] = int(self.config_path.stat().st_mtime_ns)
                return
            except OSError as e:
                last_error = e
                if attempt + 1 >= self._io_retry_attempts:
                    break
                await asyncio.sleep(self._io_retry_delay_seconds * (attempt + 1))
            finally:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
        raise RuntimeError(f"Failed to save knowledge base config: {last_error}") from last_error

    # ==================== Knowledge Base Management ====================

    async def get_knowledge_bases(self) -> List[KnowledgeBase]:
        """Get all knowledge bases"""
        config = await self.load_config()
        await self._ensure_docs_cache_loaded()
        store_key = self._doc_store_key()
        docs_map = self._docs_cache.get(store_key, {})
        counts: Dict[str, int] = {}
        for doc in docs_map.values():
            counts[doc.kb_id] = counts.get(doc.kb_id, 0) + 1

        items: List[KnowledgeBase] = []
        for kb in config.knowledge_bases:
            kb_dict = kb.model_dump()
            kb_dict["document_count"] = int(counts.get(kb.id, 0))
            items.append(KnowledgeBase(**kb_dict))
        return items

    async def get_knowledge_base(self, kb_id: str) -> Optional[KnowledgeBase]:
        """Get a specific knowledge base"""
        config = await self.load_config()
        await self._ensure_docs_cache_loaded()
        store_key = self._doc_store_key()
        docs_map = self._docs_cache.get(store_key, {})
        count = sum(1 for doc in docs_map.values() if doc.kb_id == kb_id)
        for kb in config.knowledge_bases:
            if kb.id == kb_id:
                kb_dict = kb.model_dump()
                kb_dict["document_count"] = int(count)
                return KnowledgeBase(**kb_dict)
        return None

    async def add_knowledge_base(self, kb: KnowledgeBase):
        """Add a new knowledge base"""
        async with self._mutation_lock:
            config = await self.load_config()

            if any(k.id == kb.id for k in config.knowledge_bases):
                raise ValueError(f"Knowledge base with id '{kb.id}' already exists")

            config.knowledge_bases.append(kb)
            await self.save_config(config)

        # Create storage directory
        kb_dir = self.storage_dir / kb.id / "documents"
        kb_dir.mkdir(parents=True, exist_ok=True)

    async def update_knowledge_base(self, kb_id: str, updates: dict):
        """Update knowledge base fields"""
        async with self._mutation_lock:
            config = await self.load_config()

            for i, kb in enumerate(config.knowledge_bases):
                if kb.id == kb_id:
                    kb_dict = kb.model_dump()
                    for key, value in updates.items():
                        if key in kb_dict and key not in ('id', 'created_at', 'document_count'):
                            kb_dict[key] = value
                    config.knowledge_bases[i] = KnowledgeBase(**kb_dict)
                    await self.save_config(config)
                    return config.knowledge_bases[i]

        raise ValueError(f"Knowledge base '{kb_id}' not found")

    async def delete_knowledge_base(self, kb_id: str):
        """Delete a knowledge base and all its documents"""
        async with self._mutation_lock:
            config = await self.load_config()

            # Remove the knowledge base
            config.knowledge_bases = [kb for kb in config.knowledge_bases if kb.id != kb_id]

            await self.save_config(config)

            await self._ensure_docs_cache_loaded()
            store_key = self._doc_store_key()
            async with self._docs_lock:
                docs_map = self._docs_cache.get(store_key, {})
                to_delete = [key for key, doc in docs_map.items() if doc.kb_id == kb_id]
                if to_delete:
                    for key in to_delete:
                        docs_map.pop(key, None)
                    await self._append_doc_events([{"op": "delete_kb", "kb_id": kb_id}])
                    self._docs_event_count[store_key] = int(self._docs_event_count.get(store_key, 0) or 0) + 1
                    self._docs_events_mtime_ns[store_key] = int(self.docs_events_path.stat().st_mtime_ns)
                    await self._compact_doc_events_if_needed(store_key)

        # Remove storage directory
        kb_dir = self.storage_dir / kb_id
        if kb_dir.exists():
            shutil.rmtree(kb_dir, ignore_errors=True)

        # Remove vector-store chunks
        try:
            from .rag_config_service import RagConfigService
            rag_config = RagConfigService()
            backend = str(
                getattr(rag_config.config.storage, "vector_store_backend", "chroma")
                or "chroma"
            ).lower()
            if backend == "sqlite_vec":
                from .sqlite_vec_service import SqliteVecService

                deleted = SqliteVecService().delete_kb_chunks(kb_id=kb_id)
                logger.info(f"Deleted {deleted} SQLite vector chunk(s) for kb {kb_id}")
            else:
                persist_dir = Path(rag_config.config.storage.persist_directory)
                if not persist_dir.is_absolute():
                    persist_dir = Path(__file__).parent.parent.parent.parent / persist_dir

                import chromadb
                client = chromadb.PersistentClient(path=str(persist_dir))
                collection_name = f"kb_{kb_id}"
                try:
                    client.delete_collection(collection_name)
                    logger.info(f"Deleted ChromaDB collection: {collection_name}")
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Failed to delete vector chunks for KB {kb_id}: {e}")

        try:
            from .bm25_service import Bm25Service

            bm25_service = Bm25Service()
            bm25_service.delete_kb_chunks(kb_id=kb_id)
        except Exception as e:
            logger.warning(f"Failed to delete BM25 chunks for KB {kb_id}: {e}")

    # ==================== Document Management ====================

    async def get_documents(self, kb_id: str) -> List[KnowledgeBaseDocument]:
        """Get all documents for a knowledge base"""
        await self._ensure_docs_cache_loaded()
        store_key = self._doc_store_key()
        docs_map = self._docs_cache.get(store_key, {})
        return [doc.model_copy(deep=True) for doc in docs_map.values() if doc.kb_id == kb_id]

    async def get_document(self, kb_id: str, doc_id: str) -> Optional[KnowledgeBaseDocument]:
        """Get a specific document"""
        await self._ensure_docs_cache_loaded()
        store_key = self._doc_store_key()
        docs_map = self._docs_cache.get(store_key, {})
        doc = docs_map.get(self._doc_cache_key(kb_id, doc_id))
        if doc is None:
            return None
        return doc.model_copy(deep=True)

    async def add_document(self, doc: KnowledgeBaseDocument):
        """Add a document record"""
        async with self._mutation_lock:
            await self._ensure_docs_cache_loaded()
            store_key = self._doc_store_key()
            async with self._docs_lock:
                docs_map = self._docs_cache.get(store_key, {})
                docs_map[self._doc_cache_key(doc.kb_id, doc.id)] = doc.model_copy(deep=True)
                await self._append_doc_events(
                    [
                        {
                            "op": "upsert",
                            "doc": doc.model_dump(mode="json"),
                        }
                    ]
                )
                self._docs_event_count[store_key] = int(self._docs_event_count.get(store_key, 0) or 0) + 1
                self._docs_events_mtime_ns[store_key] = int(self.docs_events_path.stat().st_mtime_ns)
                await self._compact_doc_events_if_needed(store_key)

    async def add_documents_bulk(self, docs: List[KnowledgeBaseDocument]):
        """Add multiple document records with one append-only event write."""
        if not docs:
            return

        async with self._mutation_lock:
            await self._ensure_docs_cache_loaded()
            store_key = self._doc_store_key()
            async with self._docs_lock:
                docs_map = self._docs_cache.get(store_key, {})
                events: List[Dict[str, object]] = []
                for doc in docs:
                    docs_map[self._doc_cache_key(doc.kb_id, doc.id)] = doc.model_copy(deep=True)
                    events.append(
                        {
                            "op": "upsert",
                            "doc": doc.model_dump(mode="json"),
                        }
                    )
                await self._append_doc_events(events)
                self._docs_event_count[store_key] = int(self._docs_event_count.get(store_key, 0) or 0) + len(events)
                self._docs_events_mtime_ns[store_key] = int(self.docs_events_path.stat().st_mtime_ns)
                await self._compact_doc_events_if_needed(store_key)

    async def update_document_status(
        self,
        kb_id: str,
        doc_id: str,
        status: str,
        chunk_count: int = 0,
        error_message: Optional[str] = None,
    ):
        """Update document processing status"""
        async with self._mutation_lock:
            await self._ensure_docs_cache_loaded()
            store_key = self._doc_store_key()
            async with self._docs_lock:
                docs_map = self._docs_cache.get(store_key, {})
                cache_key = self._doc_cache_key(kb_id, doc_id)
                doc = docs_map.get(cache_key)
                if doc is None:
                    raise ValueError(f"Document '{doc_id}' not found in KB '{kb_id}'")

                doc_dict = doc.model_dump()
                doc_dict['status'] = status
                doc_dict['chunk_count'] = chunk_count
                doc_dict['error_message'] = error_message
                updated = KnowledgeBaseDocument(**doc_dict)
                docs_map[cache_key] = updated
                await self._append_doc_events(
                    [
                        {
                            "op": "upsert",
                            "doc": updated.model_dump(mode="json"),
                        }
                    ]
                )
                self._docs_event_count[store_key] = int(self._docs_event_count.get(store_key, 0) or 0) + 1
                self._docs_events_mtime_ns[store_key] = int(self.docs_events_path.stat().st_mtime_ns)
                await self._compact_doc_events_if_needed(store_key)
                return

    async def delete_document(self, kb_id: str, doc_id: str):
        """Delete a document and its chunks"""
        async with self._mutation_lock:
            await self._ensure_docs_cache_loaded()
            store_key = self._doc_store_key()
            async with self._docs_lock:
                docs_map = self._docs_cache.get(store_key, {})
                cache_key = self._doc_cache_key(kb_id, doc_id)
                doc_to_delete = docs_map.pop(cache_key, None)
                if doc_to_delete is None:
                    raise ValueError(f"Document '{doc_id}' not found in KB '{kb_id}'")

                await self._append_doc_events(
                    [
                        {
                            "op": "delete",
                            "kb_id": kb_id,
                            "doc_id": doc_id,
                        }
                    ]
                )
                self._docs_event_count[store_key] = int(self._docs_event_count.get(store_key, 0) or 0) + 1
                self._docs_events_mtime_ns[store_key] = int(self.docs_events_path.stat().st_mtime_ns)
                await self._compact_doc_events_if_needed(store_key)

        # Remove file from storage
        doc_dir = self.storage_dir / kb_id / "documents"
        for file_path in doc_dir.glob(f"{doc_id}_*"):
            file_path.unlink(missing_ok=True)

        # Remove chunks from vector store
        try:
            from .rag_config_service import RagConfigService
            rag_config = RagConfigService()
            backend = str(
                getattr(rag_config.config.storage, "vector_store_backend", "chroma")
                or "chroma"
            ).lower()
            if backend == "sqlite_vec":
                from .sqlite_vec_service import SqliteVecService

                deleted = SqliteVecService().delete_document_chunks(kb_id=kb_id, doc_id=doc_id)
                logger.info(f"Deleted {deleted} SQLite vector chunk(s) for doc {doc_id}")
            else:
                persist_dir = Path(rag_config.config.storage.persist_directory)
                if not persist_dir.is_absolute():
                    persist_dir = Path(__file__).parent.parent.parent.parent / persist_dir

                import chromadb
                client = chromadb.PersistentClient(path=str(persist_dir))
                collection_name = f"kb_{kb_id}"
                try:
                    collection = client.get_collection(collection_name)
                    collection.delete(where={"doc_id": doc_id})
                    logger.info(f"Deleted ChromaDB chunks for doc {doc_id} using where filter")
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Failed to delete vector chunks for doc {doc_id}: {e}")

        try:
            from .bm25_service import Bm25Service

            bm25_service = Bm25Service()
            bm25_service.delete_document_chunks(kb_id=kb_id, doc_id=doc_id)
        except Exception as e:
            logger.warning(f"Failed to delete BM25 chunks for doc {doc_id}: {e}")

    def get_document_storage_path(self, kb_id: str, doc_id: str, filename: str) -> Path:
        """Get the storage path for a document file"""
        doc_dir = self.storage_dir / kb_id / "documents"
        doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir / f"{doc_id}_{filename}"
