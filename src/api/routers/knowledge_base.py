"""
Knowledge Base API Router

Provides CRUD endpoints for knowledge bases and document management.
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from typing import List, Optional
import logging
import uuid
import asyncio
import os
import aiofiles
from pathlib import Path

from ..models.knowledge_base import (
    KnowledgeBase,
    KnowledgeBaseDocument,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseChunk,
)
from ..services.knowledge_base_service import KnowledgeBaseService
from ..config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-bases", tags=["knowledge-bases"])

ALLOWED_EXTENSIONS = {'.txt', '.md', '.pdf', '.docx', '.html'}
UPLOAD_CHUNK_SIZE_BYTES = 1024 * 1024
MAX_KB_UPLOAD_SIZE_BYTES = max(1, int(settings.max_file_size_mb)) * 1024 * 1024


def get_kb_service() -> KnowledgeBaseService:
    """Dependency injection for KnowledgeBaseService."""
    return KnowledgeBaseService()


async def _persist_upload_file(
    upload_file: UploadFile,
    storage_path: Path,
    *,
    chunk_size_bytes: int = UPLOAD_CHUNK_SIZE_BYTES,
    max_size_bytes: int = MAX_KB_UPLOAD_SIZE_BYTES,
) -> int:
    """Persist uploaded content incrementally to avoid large in-memory buffers."""
    file_size = 0
    try:
        async with aiofiles.open(storage_path, 'wb') as f:
            while True:
                chunk = await upload_file.read(chunk_size_bytes)
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > max_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Max size is {settings.max_file_size_mb} MB",
                    )
                await f.write(chunk)
        return file_size
    except HTTPException:
        storage_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        storage_path.unlink(missing_ok=True)
        logger.error(f"Failed to persist uploaded file '{upload_file.filename}' to {storage_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")
    finally:
        try:
            await upload_file.close()
        except Exception:
            pass


# ==================== Knowledge Base CRUD ====================

@router.get("", response_model=List[KnowledgeBase])
async def list_knowledge_bases(
    service: KnowledgeBaseService = Depends(get_kb_service)
):
    """List all knowledge bases"""
    try:
        return await service.get_knowledge_bases()
    except Exception as e:
        logger.error(f"Failed to list knowledge bases: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=KnowledgeBase)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    service: KnowledgeBaseService = Depends(get_kb_service)
):
    """Create a new knowledge base"""
    try:
        kb = KnowledgeBase(
            id=data.id,
            name=data.name,
            description=data.description,
            embedding_model=data.embedding_model,
            chunk_size=data.chunk_size,
            chunk_overlap=data.chunk_overlap,
            enabled=data.enabled,
        )
        await service.add_knowledge_base(kb)
        return kb
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{kb_id}", response_model=KnowledgeBase)
async def get_knowledge_base(
    kb_id: str,
    service: KnowledgeBaseService = Depends(get_kb_service)
):
    """Get a specific knowledge base"""
    kb = await service.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")
    return kb


@router.put("/{kb_id}", response_model=KnowledgeBase)
async def update_knowledge_base(
    kb_id: str,
    data: KnowledgeBaseUpdate,
    service: KnowledgeBaseService = Depends(get_kb_service)
):
    """Update a knowledge base"""
    try:
        updates = data.model_dump(exclude_none=True)
        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")
        updated = await service.update_knowledge_base(kb_id, updates)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{kb_id}")
async def delete_knowledge_base(
    kb_id: str,
    service: KnowledgeBaseService = Depends(get_kb_service)
):
    """Delete a knowledge base and all its documents"""
    try:
        kb = await service.get_knowledge_base(kb_id)
        if not kb:
            raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")
        await service.delete_knowledge_base(kb_id)
        return {"message": f"Knowledge base '{kb_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Document Management ====================

@router.get("/{kb_id}/documents", response_model=List[KnowledgeBaseDocument])
async def list_documents(
    kb_id: str,
    service: KnowledgeBaseService = Depends(get_kb_service)
):
    """List all documents in a knowledge base"""
    kb = await service.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")
    return await service.get_documents(kb_id)


@router.post("/{kb_id}/documents/upload", response_model=KnowledgeBaseDocument)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    service: KnowledgeBaseService = Depends(get_kb_service)
):
    """Upload a document to a knowledge base"""
    kb = await service.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")

    # Validate file extension
    filename = file.filename or "unnamed"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Generate document ID
    doc_id = str(uuid.uuid4())[:8]

    # Save file to storage
    storage_path = service.get_document_storage_path(kb_id, doc_id, filename)
    file_size = await _persist_upload_file(file, storage_path)

    # Create document record with pending status
    doc = KnowledgeBaseDocument(
        id=doc_id,
        kb_id=kb_id,
        filename=filename,
        file_type=ext,
        file_size=file_size,
        status="pending",
    )
    await service.add_document(doc)

    # Trigger async processing
    asyncio.create_task(_process_document_async(kb_id, doc_id, filename, ext, storage_path))

    return doc


@router.delete("/{kb_id}/documents/{doc_id}")
async def delete_document(
    kb_id: str,
    doc_id: str,
    service: KnowledgeBaseService = Depends(get_kb_service)
):
    """Delete a document from a knowledge base"""
    try:
        doc = await service.get_document(kb_id, doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
        await service.delete_document(kb_id, doc_id)
        return {"message": f"Document '{doc_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{kb_id}/documents/{doc_id}/reprocess")
async def reprocess_document(
    kb_id: str,
    doc_id: str,
    service: KnowledgeBaseService = Depends(get_kb_service)
):
    """Re-process a document"""
    doc = await service.get_document(kb_id, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")

    # Find the stored file
    doc_dir = service.storage_dir / kb_id / "documents"
    storage_path = None
    for file_path in doc_dir.glob(f"{doc_id}_*"):
        storage_path = file_path
        break

    if not storage_path or not storage_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found on disk")

    # Reset status to pending
    await service.update_document_status(kb_id, doc_id, "pending")

    # Trigger async processing
    asyncio.create_task(_process_document_async(kb_id, doc_id, doc.filename, doc.file_type, storage_path))

    return {"message": f"Document '{doc_id}' queued for reprocessing"}


@router.get("/{kb_id}/chunks", response_model=List[KnowledgeBaseChunk])
async def list_chunks(
    kb_id: str,
    doc_id: Optional[str] = Query(None),
    limit: int = Query(200, ge=1, le=2000),
    service: KnowledgeBaseService = Depends(get_kb_service)
):
    """List chunks for a knowledge base (developer inspection)."""
    kb = await service.get_knowledge_base(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_id}' not found")

    try:
        from ..services.rag_config_service import RagConfigService
        rag_config = RagConfigService()
        backend = str(
            getattr(rag_config.config.storage, "vector_store_backend", "chroma")
            or "chroma"
        ).lower()
        items: List[KnowledgeBaseChunk] = []
        if backend == "sqlite_vec":
            from ..services.sqlite_vec_service import SqliteVecService

            rows = SqliteVecService().list_chunks(kb_id=kb_id, doc_id=doc_id, limit=limit)
            for row in rows:
                items.append(
                    KnowledgeBaseChunk(
                        id=str(row.get("id") or ""),
                        kb_id=str(row.get("kb_id") or kb_id),
                        doc_id=str(row.get("doc_id") or ""),
                        filename=str(row.get("filename") or ""),
                        chunk_index=int(row.get("chunk_index", 0) or 0),
                        content=str(row.get("content") or ""),
                    )
                )
        else:
            persist_dir = Path(rag_config.config.storage.persist_directory)
            if not persist_dir.is_absolute():
                persist_dir = Path(__file__).parent.parent.parent.parent / persist_dir

            import chromadb
            client = chromadb.PersistentClient(path=str(persist_dir))
            collection_name = f"kb_{kb_id}"
            collection = client.get_collection(collection_name)
            query = {"include": ["documents", "metadatas"]}
            if doc_id:
                query["where"] = {"doc_id": doc_id}
            data = collection.get(**query)

            documents = data.get("documents", []) or []
            metadatas = data.get("metadatas", []) or []
            ids = data.get("ids", []) or []
            for index, content in enumerate(documents):
                meta = metadatas[index] or {}
                items.append(KnowledgeBaseChunk(
                    id=ids[index],
                    kb_id=meta.get("kb_id", kb_id),
                    doc_id=meta.get("doc_id"),
                    filename=meta.get("filename"),
                    chunk_index=meta.get("chunk_index", 0),
                    content=content or "",
                ))

        items.sort(key=lambda item: (item.doc_id or "", item.chunk_index, item.id))
        return items[:limit]
    except Exception as e:
        logger.warning(f"Failed to list chunks for KB {kb_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _process_document_async(kb_id: str, doc_id: str, filename: str, file_type: str, storage_path):
    """Background task to process a document"""
    try:
        from ..services.document_processing_service import DocumentProcessingService
        processor = DocumentProcessingService()
        await processor.process_document(kb_id, doc_id, filename, file_type, str(storage_path))
    except Exception as e:
        logger.error(f"Background document processing failed for {doc_id}: {e}")
        try:
            service = KnowledgeBaseService()
            await service.update_document_status(kb_id, doc_id, "error", error_message=str(e))
        except Exception as e2:
            logger.error(f"Failed to update document status to error: {e2}")
