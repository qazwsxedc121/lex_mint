"""
Knowledge Base configuration management service

Handles loading, saving, and managing knowledge base configurations and documents.
"""
import yaml
import aiofiles
import shutil
import logging
from pathlib import Path
from typing import List, Optional
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

    def __init__(self, config_path: Path = None, storage_dir: Path = None):
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
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """Ensure configuration file exists, create default if not"""
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            default_config = {'knowledge_bases': [], 'documents': []}
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(default_config, f, allow_unicode=True, sort_keys=False)

    async def load_config(self) -> KnowledgeBasesConfig:
        """Load configuration file"""
        async with aiofiles.open(self.config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = yaml.safe_load(content) or {}
            return KnowledgeBasesConfig(**data)

    async def save_config(self, config: KnowledgeBasesConfig):
        """Save configuration file with Windows-safe write"""
        import os
        content = yaml.safe_dump(
            config.model_dump(mode='json'),
            allow_unicode=True,
            sort_keys=False
        )
        temp_path = self.config_path.with_suffix('.yaml.tmp')
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        # On Windows, Path.replace() can fail if the target is locked.
        # Retry a few times, then fall back to direct overwrite.
        import time
        for attempt in range(5):
            try:
                os.replace(str(temp_path), str(self.config_path))
                return
            except OSError:
                time.sleep(0.1)
        # Fallback: write directly
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        async with aiofiles.open(self.config_path, 'w', encoding='utf-8') as f:
            await f.write(content)

    # ==================== Knowledge Base Management ====================

    async def get_knowledge_bases(self) -> List[KnowledgeBase]:
        """Get all knowledge bases"""
        config = await self.load_config()
        return config.knowledge_bases

    async def get_knowledge_base(self, kb_id: str) -> Optional[KnowledgeBase]:
        """Get a specific knowledge base"""
        config = await self.load_config()
        for kb in config.knowledge_bases:
            if kb.id == kb_id:
                return kb
        return None

    async def add_knowledge_base(self, kb: KnowledgeBase):
        """Add a new knowledge base"""
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
        config = await self.load_config()

        # Remove the knowledge base
        config.knowledge_bases = [kb for kb in config.knowledge_bases if kb.id != kb_id]

        # Remove associated documents
        config.documents = [doc for doc in config.documents if doc.kb_id != kb_id]

        await self.save_config(config)

        # Remove storage directory
        kb_dir = self.storage_dir / kb_id
        if kb_dir.exists():
            shutil.rmtree(kb_dir, ignore_errors=True)

        # Remove ChromaDB collection
        try:
            from .rag_config_service import RagConfigService
            rag_config = RagConfigService()
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
            logger.warning(f"Failed to delete ChromaDB collection for KB {kb_id}: {e}")

    # ==================== Document Management ====================

    async def get_documents(self, kb_id: str) -> List[KnowledgeBaseDocument]:
        """Get all documents for a knowledge base"""
        config = await self.load_config()
        return [doc for doc in config.documents if doc.kb_id == kb_id]

    async def get_document(self, kb_id: str, doc_id: str) -> Optional[KnowledgeBaseDocument]:
        """Get a specific document"""
        config = await self.load_config()
        for doc in config.documents:
            if doc.kb_id == kb_id and doc.id == doc_id:
                return doc
        return None

    async def add_document(self, doc: KnowledgeBaseDocument):
        """Add a document record"""
        config = await self.load_config()
        config.documents.append(doc)

        # Update document count on KB
        for kb in config.knowledge_bases:
            if kb.id == doc.kb_id:
                kb.document_count = len([d for d in config.documents if d.kb_id == doc.kb_id])
                break

        await self.save_config(config)

    async def update_document_status(self, kb_id: str, doc_id: str, status: str,
                                      chunk_count: int = 0, error_message: str = None):
        """Update document processing status"""
        config = await self.load_config()

        for i, doc in enumerate(config.documents):
            if doc.kb_id == kb_id and doc.id == doc_id:
                doc_dict = doc.model_dump()
                doc_dict['status'] = status
                doc_dict['chunk_count'] = chunk_count
                doc_dict['error_message'] = error_message
                config.documents[i] = KnowledgeBaseDocument(**doc_dict)
                await self.save_config(config)
                return

        raise ValueError(f"Document '{doc_id}' not found in KB '{kb_id}'")

    async def delete_document(self, kb_id: str, doc_id: str):
        """Delete a document and its chunks"""
        config = await self.load_config()

        # Find and remove the document
        doc_to_delete = None
        for doc in config.documents:
            if doc.kb_id == kb_id and doc.id == doc_id:
                doc_to_delete = doc
                break

        if not doc_to_delete:
            raise ValueError(f"Document '{doc_id}' not found in KB '{kb_id}'")

        config.documents = [
            doc for doc in config.documents
            if not (doc.kb_id == kb_id and doc.id == doc_id)
        ]

        # Update document count on KB
        for kb in config.knowledge_bases:
            if kb.id == kb_id:
                kb.document_count = len([d for d in config.documents if d.kb_id == kb_id])
                break

        await self.save_config(config)

        # Remove file from storage
        doc_dir = self.storage_dir / kb_id / "documents"
        for file_path in doc_dir.glob(f"{doc_id}_*"):
            file_path.unlink(missing_ok=True)

        # Remove chunks from ChromaDB
        try:
            from .rag_config_service import RagConfigService
            rag_config = RagConfigService()
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
            logger.warning(f"Failed to delete ChromaDB chunks for doc {doc_id}: {e}")

    def get_document_storage_path(self, kb_id: str, doc_id: str, filename: str) -> Path:
        """Get the storage path for a document file"""
        doc_dir = self.storage_dir / kb_id / "documents"
        doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir / f"{doc_id}_{filename}"
