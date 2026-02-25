"""
Document Processing Service

Pipeline: Upload -> Extract Text -> Chunk -> Embed -> Store in vector backend
"""
import logging
import random
import asyncio
import uuid
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """Service for processing documents into vector embeddings"""

    def __init__(self):
        from .rag_config_service import RagConfigService
        from .embedding_service import EmbeddingService
        from .bm25_service import Bm25Service
        self.rag_config_service = RagConfigService()
        self.embedding_service = EmbeddingService()
        self.bm25_service = Bm25Service()
        self._sqlite_vec_service = None

    def _get_sqlite_vec_service(self):
        from .sqlite_vec_service import SqliteVecService

        service = getattr(self, "_sqlite_vec_service", None)
        if service is None:
            service = SqliteVecService()
            self._sqlite_vec_service = service
        return service

    async def process_document(
        self,
        kb_id: str,
        doc_id: str,
        filename: str,
        file_type: str,
        file_path: str,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        track_status: bool = True,
        kb_snapshot=None,
    ):
        """
        Process a document: extract text, chunk, embed, store in vector backend.

        Args:
            kb_id: Knowledge base ID
            doc_id: Document ID
            filename: Original filename
            file_type: File extension (e.g., .pdf)
            file_path: Path to the uploaded file
            chunk_size: Override chunk size (uses KB config or global config)
            chunk_overlap: Override chunk overlap
        """
        from .knowledge_base_service import KnowledgeBaseService
        kb_service = KnowledgeBaseService()

        try:
            # Update status to processing
            if track_status:
                await kb_service.update_document_status(kb_id, doc_id, "processing")

            # Get chunk settings from KB override or global config
            kb = kb_snapshot if kb_snapshot is not None else await kb_service.get_knowledge_base(kb_id)
            effective_chunk_size = chunk_size or (kb.chunk_size if kb and kb.chunk_size else self.rag_config_service.config.chunking.chunk_size)
            effective_chunk_overlap = chunk_overlap or (kb.chunk_overlap if kb and kb.chunk_overlap else self.rag_config_service.config.chunking.chunk_overlap)

            # Step 1: Extract text
            logger.info(f"Extracting text from {filename} ({file_type})")
            text = self._extract_text(file_path, file_type)
            if not text or not text.strip():
                raise ValueError("No text content extracted from document")
            logger.info(f"Extracted {len(text)} characters from {filename}")

            # Step 2: Chunk text (semantic-first)
            logger.info(f"Chunking text with size={effective_chunk_size}, overlap={effective_chunk_overlap}")
            chunks = self._chunk_text(text, file_type, effective_chunk_size, effective_chunk_overlap)
            logger.info(f"Created {len(chunks)} chunks from {filename}")

            if not chunks:
                raise ValueError("No chunks created from document text")

            # Step 3: Get embedding function
            override_model = kb.embedding_model if kb and kb.embedding_model else None
            embedding_fn = self.embedding_service.get_embedding_function(override_model)

            # Step 4: Store in configured vector backend
            vector_backend = str(
                getattr(self.rag_config_service.config.storage, "vector_store_backend", "chroma")
                or "chroma"
            ).lower()
            if vector_backend == "sqlite_vec":
                logger.info(f"Storing {len(chunks)} chunks in SQLite vector store for kb_{kb_id}")
                await self._store_in_sqlite_vec(
                    kb_id=kb_id,
                    doc_id=doc_id,
                    filename=filename,
                    file_type=file_type,
                    chunks=chunks,
                    embedding_fn=embedding_fn,
                )
            else:
                logger.info(f"Storing {len(chunks)} chunks in ChromaDB collection kb_{kb_id}")
                await self._store_in_chromadb(
                    kb_id=kb_id,
                    doc_id=doc_id,
                    filename=filename,
                    file_type=file_type,
                    chunks=chunks,
                    embedding_fn=embedding_fn,
                )

            # Step 5: Update document status to ready
            if track_status:
                await kb_service.update_document_status(
                    kb_id, doc_id, "ready",
                    chunk_count=len(chunks)
                )
            logger.info(f"Document {doc_id} ({filename}) processed successfully: {len(chunks)} chunks")
            return len(chunks)

        except Exception as e:
            logger.error(f"Document processing failed for {doc_id} ({filename}): {e}")
            if track_status:
                try:
                    await kb_service.update_document_status(
                        kb_id, doc_id, "error",
                        error_message=str(e)
                    )
                except Exception as e2:
                    logger.error(f"Failed to update document status to error: {e2}")
            raise

    def _extract_text(self, file_path: str, file_type: str) -> str:
        """Extract text content from a file based on its type"""
        file_type = file_type.lower()

        if file_type in ('.txt', '.md'):
            return self._extract_text_plain(file_path)
        elif file_type == '.pdf':
            return self._extract_text_pdf(file_path)
        elif file_type == '.docx':
            return self._extract_text_docx(file_path)
        elif file_type in ('.html', '.htm'):
            return self._extract_text_html(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    def _extract_text_plain(self, file_path: str) -> str:
        """Extract text from plain text files (txt, md)"""
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        # Fallback: read as bytes and decode with errors='replace'
        with open(file_path, 'rb') as f:
            return f.read().decode('utf-8', errors='replace')

    def _extract_text_pdf(self, file_path: str) -> str:
        """Extract text from PDF files."""
        # PyMuPDF handles many CJK PDFs better than pypdf when ToUnicode maps are missing.
        try:
            import fitz

            doc = fitz.open(file_path)
            text_parts = []
            for page in doc:
                page_text = page.get_text("text")
                if page_text and page_text.strip():
                    text_parts.append(page_text)
            if text_parts:
                return "\n\n".join(text_parts)
            logger.warning("PyMuPDF extracted empty text from PDF: %s", file_path)
        except ModuleNotFoundError:
            logger.debug("PyMuPDF not installed, falling back to pypdf for: %s", file_path)
        except Exception as e:
            logger.warning("PyMuPDF extraction failed for %s: %s, falling back to pypdf", file_path, e)

        from pypdf import PdfReader

        reader = PdfReader(file_path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                text_parts.append(page_text)
        return "\n\n".join(text_parts)

    def _extract_text_docx(self, file_path: str) -> str:
        """Extract text from DOCX files"""
        from docx import Document
        doc = Document(file_path)
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        return "\n\n".join(text_parts)

    def _extract_text_html(self, file_path: str) -> str:
        """Extract text from HTML files using trafilatura"""
        try:
            import trafilatura
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            text = trafilatura.extract(html_content)
            if text:
                return text
        except Exception as e:
            logger.warning(f"Trafilatura extraction failed: {e}, falling back to plain read")

        # Fallback: read as plain text
        return self._extract_text_plain(file_path)

    def _chunk_text(self, text: str, file_type: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """Split text into semantic chunks first, then merge into size-limited chunks."""
        units = self._semantic_units(text, file_type, chunk_size, chunk_overlap)
        if not units:
            return self._fallback_recursive_chunks(text, chunk_size, chunk_overlap)
        return self._merge_units(units, chunk_size, chunk_overlap)

    def _semantic_units(self, text: str, file_type: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """Create semantic units (sections/paragraphs) before merging into chunks."""
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized:
            return []

        file_type = (file_type or "").lower()
        if file_type in (".md", ".markdown"):
            units = self._split_markdown_sections(normalized)
        else:
            units = self._split_paragraphs(normalized)

        # Split oversized units with a fallback splitter
        refined_units: List[str] = []
        for unit in units:
            if len(unit) <= chunk_size:
                refined_units.append(unit)
                continue
            refined_units.extend(self._fallback_recursive_chunks(unit, chunk_size, chunk_overlap))
        return refined_units

    def _split_markdown_sections(self, text: str) -> List[str]:
        """Split markdown into sections by heading, keeping heading with its content."""
        lines = text.split("\n")
        sections: List[str] = []
        current: List[str] = []
        for line in lines:
            if line.strip().startswith("#"):
                if current:
                    sections.append("\n".join(current).strip())
                    current = []
            current.append(line)
        if current:
            sections.append("\n".join(current).strip())
        return [s for s in sections if s]

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs (blank-line delimited)."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        return paragraphs

    def _merge_units(self, units: List[str], chunk_size: int, chunk_overlap: int) -> List[str]:
        """Merge semantic units into size-limited chunks with overlap."""
        chunks: List[str] = []
        current_units: List[str] = []
        current_len = 0

        def flush_current() -> None:
            nonlocal current_units, current_len
            if not current_units:
                return
            chunk = "\n\n".join(current_units).strip()
            if chunk:
                chunks.append(chunk)
            if chunk_overlap <= 0:
                current_units = []
                current_len = 0
                return
            # Build overlap by keeping trailing units up to overlap size
            overlap_units: List[str] = []
            overlap_len = 0
            for unit in reversed(current_units):
                overlap_len += len(unit)
                overlap_units.append(unit)
                if overlap_len >= chunk_overlap:
                    break
            overlap_units.reverse()
            current_units = overlap_units
            current_len = sum(len(u) for u in current_units) + max(0, len(current_units) - 1) * 2

        for unit in units:
            unit = unit.strip()
            if not unit:
                continue
            unit_len = len(unit)
            # +2 for "\n\n" separator
            projected = current_len + unit_len + (2 if current_units else 0)
            if current_units and projected > chunk_size:
                flush_current()
                # Recompute projected after flush
                projected = current_len + unit_len + (2 if current_units else 0)
            current_units.append(unit)
            current_len = projected

        flush_current()
        return [c for c in chunks if c]

    def _fallback_recursive_chunks(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """Fallback splitter for oversized units or non-structured text."""
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        return splitter.split_text(text)

    async def _store_in_chromadb(
        self,
        kb_id: str,
        doc_id: str,
        filename: str,
        file_type: str,
        chunks: List[str],
        embedding_fn,
    ):
        """Store document chunks in ChromaDB"""
        from langchain_chroma import Chroma
        from chromadb.errors import InvalidArgumentError

        persist_dir = Path(self.rag_config_service.config.storage.persist_directory)
        if not persist_dir.is_absolute():
            persist_dir = Path(__file__).parent.parent.parent.parent / persist_dir
        persist_dir.mkdir(parents=True, exist_ok=True)

        collection_name = f"kb_{kb_id}"

        # Create or get the vector store
        vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=embedding_fn,
            persist_directory=str(persist_dir),
            collection_metadata={"hnsw:space": "cosine"},
        )

        # Write a new document generation first, then clean stale generations.
        # This keeps old chunks serving if re-indexing fails midway.
        ingest_id = uuid.uuid4().hex[:8]
        ids = [f"{doc_id}_{ingest_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "kb_id": kb_id,
                "doc_id": doc_id,
                "filename": filename,
                "file_type": file_type,
                "chunk_index": i,
                "ingest_id": ingest_id,
            }
            for i in range(len(chunks))
        ]

        batch_size = max(1, int(getattr(self.rag_config_service.config.embedding, "batch_size", 64) or 64))
        batch_delay = max(0.0, float(getattr(self.rag_config_service.config.embedding, "batch_delay_seconds", 0.5) or 0.0))
        max_retries = int(getattr(self.rag_config_service.config.embedding, "batch_max_retries", 3) or 0)
        max_delay = 60.0

        total = len(chunks)
        added_ids: List[str] = []
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch_texts = chunks[start:end]
            batch_ids = ids[start:end]
            batch_metas = metadatas[start:end]

            attempt = 0
            retry_delay = batch_delay or 0.5
            while True:
                try:
                    vectorstore.add_texts(
                        texts=batch_texts,
                        ids=batch_ids,
                        metadatas=batch_metas,
                    )
                    added_ids.extend(batch_ids)
                    logger.info(f"Stored chunks {start + 1}-{end} of {total} in '{collection_name}'")
                    break
                except InvalidArgumentError as e:
                    if added_ids:
                        try:
                            vectorstore._collection.delete(ids=added_ids)
                        except Exception:
                            pass
                    raise e
                except Exception as e:
                    message = str(e).lower()
                    is_rate_limit = "rate limit" in message or "429" in message
                    attempt += 1
                    enforce_retries = max_retries > 0 and not is_rate_limit
                    if enforce_retries and attempt > max_retries:
                        if added_ids:
                            try:
                                vectorstore._collection.delete(ids=added_ids)
                            except Exception:
                                pass
                        raise e

                    if is_rate_limit:
                        retry_delay = max(retry_delay, 5.0)
                    wait_seconds = min(max_delay, max(retry_delay, batch_delay, 0.5))
                    wait_seconds *= random.uniform(0.8, 1.2)
                    max_label = "∞" if is_rate_limit or max_retries <= 0 else str(max_retries)
                    logger.warning(
                        f"Embedding batch {start + 1}-{end} failed "
                        f"(attempt {attempt}/{max_label}). Retrying in {wait_seconds:.2f}s: {e}"
                    )
                    await asyncio.sleep(wait_seconds)
                    retry_delay = min(max_delay, max(retry_delay * 2, batch_delay, 0.5))

            if batch_delay > 0 and end < total:
                await asyncio.sleep(batch_delay)

        bm25_chunks = [
            {
                "chunk_id": ids[index],
                "chunk_index": metadatas[index]["chunk_index"],
                "content": chunks[index],
            }
            for index in range(total)
        ]
        try:
            self.bm25_service.upsert_document_chunks(
                kb_id=kb_id,
                doc_id=doc_id,
                filename=filename,
                chunks=bm25_chunks,
            )
        except Exception:
            if added_ids:
                try:
                    vectorstore._collection.delete(ids=added_ids)
                except Exception:
                    pass
            raise

        # Keep only the newest generation for this document.
        try:
            existing = vectorstore._collection.get(where={"doc_id": doc_id}, include=[])
            existing_ids = existing.get("ids", []) or []
            current_ids = set(ids)
            stale_ids = [chunk_id for chunk_id in existing_ids if chunk_id not in current_ids]
            if stale_ids:
                vectorstore._collection.delete(ids=stale_ids)
                logger.info(
                    f"Removed {len(stale_ids)} stale chunks for doc {doc_id} in '{collection_name}'"
                )
        except Exception as e:
            logger.warning(f"Failed to cleanup stale chunks for doc {doc_id}: {e}")

    async def _store_in_sqlite_vec(
        self,
        kb_id: str,
        doc_id: str,
        filename: str,
        file_type: str,
        chunks: List[str],
        embedding_fn,
    ):
        """Store document chunks in SQLite vector store."""
        if not hasattr(embedding_fn, "embed_documents"):
            raise ValueError("Embedding function does not support embed_documents() for sqlite_vec backend")

        sqlite_vec_service = self._get_sqlite_vec_service()
        ingest_id = uuid.uuid4().hex[:8]
        ids = [f"{doc_id}_{ingest_id}_chunk_{i}" for i in range(len(chunks))]

        batch_size = max(1, int(getattr(self.rag_config_service.config.embedding, "batch_size", 64) or 64))
        batch_delay = max(
            0.0,
            float(getattr(self.rag_config_service.config.embedding, "batch_delay_seconds", 0.5) or 0.0),
        )
        max_retries = int(getattr(self.rag_config_service.config.embedding, "batch_max_retries", 3) or 0)
        max_delay = 60.0

        total = len(chunks)
        chunk_rows: List[dict] = []
        for start in range(0, total, batch_size):
            end = min(start + batch_size, total)
            batch_texts = chunks[start:end]
            batch_ids = ids[start:end]

            attempt = 0
            retry_delay = batch_delay or 0.5
            while True:
                try:
                    batch_vectors = embedding_fn.embed_documents(batch_texts)
                    if len(batch_vectors) != len(batch_texts):
                        raise ValueError(
                            f"Embedding result count mismatch: expected {len(batch_texts)}, got {len(batch_vectors)}"
                        )
                    for offset, vector in enumerate(batch_vectors):
                        chunk_rows.append(
                            {
                                "chunk_id": batch_ids[offset],
                                "chunk_index": start + offset,
                                "content": batch_texts[offset],
                                "embedding": vector,
                            }
                        )
                    logger.info(f"Embedded chunks {start + 1}-{end} of {total} for kb_{kb_id}")
                    break
                except Exception as e:
                    message = str(e).lower()
                    is_rate_limit = "rate limit" in message or "429" in message
                    attempt += 1
                    enforce_retries = max_retries > 0 and not is_rate_limit
                    if enforce_retries and attempt > max_retries:
                        raise e

                    if is_rate_limit:
                        retry_delay = max(retry_delay, 5.0)
                    wait_seconds = min(max_delay, max(retry_delay, batch_delay, 0.5))
                    wait_seconds *= random.uniform(0.8, 1.2)
                    max_label = "inf" if is_rate_limit or max_retries <= 0 else str(max_retries)
                    logger.warning(
                        f"Embedding batch {start + 1}-{end} failed "
                        f"(attempt {attempt}/{max_label}). Retrying in {wait_seconds:.2f}s: {e}"
                    )
                    await asyncio.sleep(wait_seconds)
                    retry_delay = min(max_delay, max(retry_delay * 2, batch_delay, 0.5))

            if batch_delay > 0 and end < total:
                await asyncio.sleep(batch_delay)

        had_existing_chunks = sqlite_vec_service.upsert_chunks(
            kb_id=kb_id,
            doc_id=doc_id,
            filename=filename,
            file_type=file_type,
            ingest_id=ingest_id,
            chunk_rows=chunk_rows,
        )

        bm25_chunks = [
            {
                "chunk_id": ids[index],
                "chunk_index": index,
                "content": chunks[index],
            }
            for index in range(total)
        ]
        try:
            self.bm25_service.upsert_document_chunks(
                kb_id=kb_id,
                doc_id=doc_id,
                filename=filename,
                chunks=bm25_chunks,
            )
        except Exception:
            sqlite_vec_service.delete_chunks_by_ids(kb_id=kb_id, chunk_ids=ids)
            raise

        if had_existing_chunks:
            deleted = sqlite_vec_service.delete_stale_document_chunks(
                kb_id=kb_id,
                doc_id=doc_id,
                keep_chunk_ids=ids,
            )
            if deleted:
                logger.info(f"Removed {deleted} stale SQLite chunks for doc {doc_id} in kb_{kb_id}")
