"""
RAG Config Service

Manages configuration for RAG (Retrieval-Augmented Generation) settings.
"""
import logging
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass, field

import yaml

from ..paths import data_state_dir, legacy_config_dir, ensure_local_file

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingConfig:
    provider: str = "api"
    api_model: str = "jina-embeddings-v3"
    api_base_url: str = ""
    api_key: str = ""
    local_model: str = "all-MiniLM-L6-v2"
    local_device: str = "cpu"
    local_gguf_model_path: str = "models/embeddings/qwen3-embedding-0.6b.gguf"
    local_gguf_n_ctx: int = 2048
    local_gguf_n_threads: int = 0
    local_gguf_n_gpu_layers: int = 0
    local_gguf_normalize: bool = True
    batch_size: int = 64
    batch_delay_seconds: float = 0.5
    batch_max_retries: int = 3


@dataclass
class ChunkingConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 200


@dataclass
class RetrievalConfig:
    retrieval_mode: str = "hybrid"
    top_k: int = 5
    score_threshold: float = 0.65
    recall_k: int = 20
    vector_recall_k: int = 5
    bm25_recall_k: int = 20
    bm25_min_term_coverage: float = 0.35
    fusion_top_k: int = 30
    fusion_strategy: str = "rrf"
    rrf_k: int = 40
    vector_weight: float = 0.05
    bm25_weight: float = 1.0
    max_per_doc: int = 2
    reorder_strategy: str = "long_context"
    context_neighbor_window: int = 0
    context_neighbor_max_total: int = 0
    context_neighbor_dedup_coverage: float = 0.9
    retrieval_query_planner_enabled: bool = False
    retrieval_query_planner_model_id: str = "auto"
    retrieval_query_planner_max_queries: int = 3
    retrieval_query_planner_timeout_seconds: int = 4
    structured_source_context_enabled: bool = False
    query_transform_enabled: bool = False
    query_transform_mode: str = "rewrite"
    query_transform_model_id: str = "auto"
    query_transform_timeout_seconds: int = 4
    query_transform_guard_enabled: bool = True
    query_transform_guard_max_new_terms: int = 2
    query_transform_crag_enabled: bool = True
    query_transform_crag_lower_threshold: float = 0.35
    query_transform_crag_upper_threshold: float = 0.75
    rerank_enabled: bool = False
    rerank_api_model: str = "jina-reranker-v2-base-multilingual"
    rerank_api_base_url: str = "https://api.jina.ai/v1/rerank"
    rerank_api_key: str = ""
    rerank_timeout_seconds: int = 20
    rerank_weight: float = 0.7


@dataclass
class StorageConfig:
    vector_store_backend: str = "sqlite_vec"
    vector_sqlite_path: str = "data/state/rag_vec.sqlite3"
    persist_directory: str = "data/chromadb"
    bm25_sqlite_path: str = "data/state/rag_bm25.sqlite3"


@dataclass
class RagConfig:
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)


class RagConfigService:
    """Service for managing RAG configuration"""

    def __init__(self, config_path: Optional[str | Path] = None):
        if config_path is None:
            resolved_config_path = data_state_dir() / "rag_config.yaml"
        else:
            resolved_config_path = Path(config_path)

        self.config_path: Path = resolved_config_path
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        """Create default config file if it doesn't exist"""
        if not self.config_path.exists():
            default_data = {
                'embedding': {
                    'provider': 'api',
                    'api_model': 'jina-embeddings-v3',
                    'api_base_url': 'https://api.jina.ai/v1',
                    'api_key': '',
                    'local_model': 'all-MiniLM-L6-v2',
                    'local_device': 'cpu',
                    'local_gguf_model_path': 'models/embeddings/qwen3-embedding-0.6b.gguf',
                    'local_gguf_n_ctx': 2048,
                    'local_gguf_n_threads': 0,
                    'local_gguf_n_gpu_layers': 0,
                    'local_gguf_normalize': True,
                    'batch_size': 64,
                    'batch_delay_seconds': 0.5,
                    'batch_max_retries': 3,
                },
                'chunking': {
                    'chunk_size': 1000,
                    'chunk_overlap': 200,
                },
                'retrieval': {
                    'retrieval_mode': 'hybrid',
                    'top_k': 5,
                    'score_threshold': 0.65,
                    'recall_k': 20,
                    'vector_recall_k': 5,
                    'bm25_recall_k': 20,
                    'bm25_min_term_coverage': 0.35,
                    'fusion_top_k': 30,
                    'fusion_strategy': 'rrf',
                    'rrf_k': 40,
                    'vector_weight': 0.05,
                    'bm25_weight': 1.0,
                    'max_per_doc': 2,
                    'reorder_strategy': 'long_context',
                    'context_neighbor_window': 0,
                    'context_neighbor_max_total': 0,
                    'context_neighbor_dedup_coverage': 0.9,
                    'retrieval_query_planner_enabled': False,
                    'retrieval_query_planner_model_id': 'auto',
                    'retrieval_query_planner_max_queries': 3,
                    'retrieval_query_planner_timeout_seconds': 4,
                    'structured_source_context_enabled': False,
                    'query_transform_enabled': False,
                    'query_transform_mode': 'rewrite',
                    'query_transform_model_id': 'auto',
                    'query_transform_timeout_seconds': 4,
                    'query_transform_guard_enabled': True,
                    'query_transform_guard_max_new_terms': 2,
                    'query_transform_crag_enabled': True,
                    'query_transform_crag_lower_threshold': 0.35,
                    'query_transform_crag_upper_threshold': 0.75,
                    'rerank_enabled': False,
                    'rerank_api_model': 'jina-reranker-v2-base-multilingual',
                    'rerank_api_base_url': 'https://api.jina.ai/v1/rerank',
                    'rerank_api_key': '',
                    'rerank_timeout_seconds': 20,
                    'rerank_weight': 0.7,
                },
                'storage': {
                    'vector_store_backend': 'sqlite_vec',
                    'vector_sqlite_path': 'data/state/rag_vec.sqlite3',
                    'persist_directory': 'data/chromadb',
                    'bm25_sqlite_path': 'data/state/rag_bm25.sqlite3',
                },
            }
            initial_text = yaml.safe_dump(default_data, allow_unicode=True, sort_keys=False)
            ensure_local_file(
                local_path=self.config_path,
                defaults_path=None,
                legacy_paths=[legacy_config_dir() / "rag_config.yaml"],
                initial_text=initial_text,
            )
            logger.info(f"Created default RAG config at {self.config_path}")

    def _load_config(self) -> RagConfig:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            embedding_data = data.get('embedding', {})
            chunking_data = data.get('chunking', {})
            retrieval_data = data.get('retrieval', {})
            storage_data = data.get('storage', {})

            return RagConfig(
                embedding=EmbeddingConfig(
                    provider=embedding_data.get('provider', 'api'),
                    api_model=embedding_data.get('api_model', 'jina-embeddings-v3'),
                    api_base_url=embedding_data.get('api_base_url', ''),
                    api_key=embedding_data.get('api_key', ''),
                    local_model=embedding_data.get('local_model', 'all-MiniLM-L6-v2'),
                    local_device=embedding_data.get('local_device', 'cpu'),
                    local_gguf_model_path=embedding_data.get(
                        'local_gguf_model_path',
                        'models/embeddings/qwen3-embedding-0.6b.gguf'
                    ),
                    local_gguf_n_ctx=embedding_data.get('local_gguf_n_ctx', 2048),
                    local_gguf_n_threads=embedding_data.get('local_gguf_n_threads', 0),
                    local_gguf_n_gpu_layers=embedding_data.get('local_gguf_n_gpu_layers', 0),
                    local_gguf_normalize=embedding_data.get('local_gguf_normalize', True),
                    batch_size=embedding_data.get('batch_size', 64),
                    batch_delay_seconds=embedding_data.get('batch_delay_seconds', 0.5),
                    batch_max_retries=embedding_data.get('batch_max_retries', 3),
                ),
                chunking=ChunkingConfig(
                    chunk_size=chunking_data.get('chunk_size', 1000),
                    chunk_overlap=chunking_data.get('chunk_overlap', 200),
                ),
                retrieval=RetrievalConfig(
                    retrieval_mode=retrieval_data.get('retrieval_mode', 'hybrid'),
                    top_k=retrieval_data.get('top_k', 5),
                    score_threshold=retrieval_data.get('score_threshold', 0.65),
                    recall_k=retrieval_data.get('recall_k', 20),
                    vector_recall_k=retrieval_data.get(
                        'vector_recall_k',
                        5,
                    ),
                    bm25_recall_k=retrieval_data.get(
                        'bm25_recall_k',
                        retrieval_data.get('recall_k', 20),
                    ),
                    bm25_min_term_coverage=retrieval_data.get('bm25_min_term_coverage', 0.35),
                    fusion_top_k=retrieval_data.get('fusion_top_k', 30),
                    fusion_strategy=retrieval_data.get('fusion_strategy', 'rrf'),
                    rrf_k=retrieval_data.get('rrf_k', 40),
                    vector_weight=retrieval_data.get('vector_weight', 0.05),
                    bm25_weight=retrieval_data.get('bm25_weight', 1.0),
                    max_per_doc=retrieval_data.get('max_per_doc', 2),
                    reorder_strategy=retrieval_data.get('reorder_strategy', 'long_context'),
                    context_neighbor_window=retrieval_data.get('context_neighbor_window', 0),
                    context_neighbor_max_total=retrieval_data.get('context_neighbor_max_total', 0),
                    context_neighbor_dedup_coverage=retrieval_data.get('context_neighbor_dedup_coverage', 0.9),
                    retrieval_query_planner_enabled=retrieval_data.get(
                        'retrieval_query_planner_enabled',
                        False,
                    ),
                    retrieval_query_planner_model_id=retrieval_data.get(
                        'retrieval_query_planner_model_id',
                        'auto',
                    ),
                    retrieval_query_planner_max_queries=retrieval_data.get(
                        'retrieval_query_planner_max_queries',
                        3,
                    ),
                    retrieval_query_planner_timeout_seconds=retrieval_data.get(
                        'retrieval_query_planner_timeout_seconds',
                        4,
                    ),
                    structured_source_context_enabled=retrieval_data.get(
                        'structured_source_context_enabled',
                        False,
                    ),
                    query_transform_enabled=retrieval_data.get('query_transform_enabled', False),
                    query_transform_mode=retrieval_data.get('query_transform_mode', 'rewrite'),
                    query_transform_model_id=retrieval_data.get('query_transform_model_id', 'auto'),
                    query_transform_timeout_seconds=retrieval_data.get('query_transform_timeout_seconds', 4),
                    query_transform_guard_enabled=retrieval_data.get('query_transform_guard_enabled', True),
                    query_transform_guard_max_new_terms=retrieval_data.get(
                        'query_transform_guard_max_new_terms',
                        2,
                    ),
                    query_transform_crag_enabled=retrieval_data.get('query_transform_crag_enabled', True),
                    query_transform_crag_lower_threshold=retrieval_data.get(
                        'query_transform_crag_lower_threshold',
                        0.35,
                    ),
                    query_transform_crag_upper_threshold=retrieval_data.get(
                        'query_transform_crag_upper_threshold',
                        0.75,
                    ),
                    rerank_enabled=retrieval_data.get('rerank_enabled', False),
                    rerank_api_model=retrieval_data.get(
                        'rerank_api_model',
                        'jina-reranker-v2-base-multilingual',
                    ),
                    rerank_api_base_url=retrieval_data.get(
                        'rerank_api_base_url',
                        'https://api.jina.ai/v1/rerank',
                    ),
                    rerank_api_key=retrieval_data.get('rerank_api_key', ''),
                    rerank_timeout_seconds=retrieval_data.get('rerank_timeout_seconds', 20),
                    rerank_weight=retrieval_data.get('rerank_weight', 0.7),
                ),
                storage=StorageConfig(
                    vector_store_backend=storage_data.get('vector_store_backend', 'sqlite_vec'),
                    vector_sqlite_path=storage_data.get('vector_sqlite_path', 'data/state/rag_vec.sqlite3'),
                    persist_directory=storage_data.get('persist_directory', 'data/chromadb'),
                    bm25_sqlite_path=storage_data.get('bm25_sqlite_path', 'data/state/rag_bm25.sqlite3'),
                ),
            )
        except Exception as e:
            logger.error(f"Failed to load RAG config: {e}")
            return RagConfig()

    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()

    def save_config(self, updates: Dict):
        """Save updated configuration to file"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # Update nested sections
            for section_key, section_updates in updates.items():
                if section_key in ('embedding', 'chunking', 'retrieval', 'storage'):
                    if section_key not in data:
                        data[section_key] = {}
                    if isinstance(section_updates, dict):
                        for key, value in section_updates.items():
                            if value is not None:
                                data[section_key][key] = value
                    else:
                        data[section_key] = section_updates

            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

            self.reload_config()
            logger.info("RAG config updated successfully")
        except Exception as e:
            logger.error(f"Failed to save RAG config: {e}")
            raise

    def get_flat_config(self) -> Dict:
        """Return config as flat dictionary for API response"""
        return {
            'embedding_provider': self.config.embedding.provider,
            'embedding_api_model': self.config.embedding.api_model,
            'embedding_api_base_url': self.config.embedding.api_base_url,
            'embedding_api_key': self.config.embedding.api_key,
            'embedding_local_model': self.config.embedding.local_model,
            'embedding_local_device': self.config.embedding.local_device,
            'embedding_local_gguf_model_path': self.config.embedding.local_gguf_model_path,
            'embedding_local_gguf_n_ctx': self.config.embedding.local_gguf_n_ctx,
            'embedding_local_gguf_n_threads': self.config.embedding.local_gguf_n_threads,
            'embedding_local_gguf_n_gpu_layers': self.config.embedding.local_gguf_n_gpu_layers,
            'embedding_local_gguf_normalize': self.config.embedding.local_gguf_normalize,
            'embedding_batch_size': self.config.embedding.batch_size,
            'embedding_batch_delay_seconds': self.config.embedding.batch_delay_seconds,
            'embedding_batch_max_retries': self.config.embedding.batch_max_retries,
            'chunk_size': self.config.chunking.chunk_size,
            'chunk_overlap': self.config.chunking.chunk_overlap,
            'retrieval_mode': self.config.retrieval.retrieval_mode,
            'top_k': self.config.retrieval.top_k,
            'score_threshold': self.config.retrieval.score_threshold,
            'recall_k': self.config.retrieval.recall_k,
            'vector_recall_k': self.config.retrieval.vector_recall_k,
            'bm25_recall_k': self.config.retrieval.bm25_recall_k,
            'bm25_min_term_coverage': self.config.retrieval.bm25_min_term_coverage,
            'fusion_top_k': self.config.retrieval.fusion_top_k,
            'fusion_strategy': self.config.retrieval.fusion_strategy,
            'rrf_k': self.config.retrieval.rrf_k,
            'vector_weight': self.config.retrieval.vector_weight,
            'bm25_weight': self.config.retrieval.bm25_weight,
            'max_per_doc': self.config.retrieval.max_per_doc,
            'reorder_strategy': self.config.retrieval.reorder_strategy,
            'context_neighbor_window': self.config.retrieval.context_neighbor_window,
            'context_neighbor_max_total': self.config.retrieval.context_neighbor_max_total,
            'context_neighbor_dedup_coverage': self.config.retrieval.context_neighbor_dedup_coverage,
            'retrieval_query_planner_enabled': self.config.retrieval.retrieval_query_planner_enabled,
            'retrieval_query_planner_model_id': self.config.retrieval.retrieval_query_planner_model_id,
            'retrieval_query_planner_max_queries': self.config.retrieval.retrieval_query_planner_max_queries,
            'retrieval_query_planner_timeout_seconds': self.config.retrieval.retrieval_query_planner_timeout_seconds,
            'structured_source_context_enabled': self.config.retrieval.structured_source_context_enabled,
            'query_transform_enabled': self.config.retrieval.query_transform_enabled,
            'query_transform_mode': self.config.retrieval.query_transform_mode,
            'query_transform_model_id': self.config.retrieval.query_transform_model_id,
            'query_transform_timeout_seconds': self.config.retrieval.query_transform_timeout_seconds,
            'query_transform_guard_enabled': self.config.retrieval.query_transform_guard_enabled,
            'query_transform_guard_max_new_terms': self.config.retrieval.query_transform_guard_max_new_terms,
            'query_transform_crag_enabled': self.config.retrieval.query_transform_crag_enabled,
            'query_transform_crag_lower_threshold': self.config.retrieval.query_transform_crag_lower_threshold,
            'query_transform_crag_upper_threshold': self.config.retrieval.query_transform_crag_upper_threshold,
            'rerank_enabled': self.config.retrieval.rerank_enabled,
            'rerank_api_model': self.config.retrieval.rerank_api_model,
            'rerank_api_base_url': self.config.retrieval.rerank_api_base_url,
            'rerank_api_key': self.config.retrieval.rerank_api_key,
            'rerank_timeout_seconds': self.config.retrieval.rerank_timeout_seconds,
            'rerank_weight': self.config.retrieval.rerank_weight,
            'vector_store_backend': self.config.storage.vector_store_backend,
            'vector_sqlite_path': self.config.storage.vector_sqlite_path,
            'persist_directory': self.config.storage.persist_directory,
            'bm25_sqlite_path': self.config.storage.bm25_sqlite_path,
        }

    def save_flat_config(self, flat_updates: Dict):
        """Save from flat dictionary format (from API)"""
        nested = {}
        mapping = {
            'embedding_provider': ('embedding', 'provider'),
            'embedding_api_model': ('embedding', 'api_model'),
            'embedding_api_base_url': ('embedding', 'api_base_url'),
            'embedding_api_key': ('embedding', 'api_key'),
            'embedding_local_model': ('embedding', 'local_model'),
            'embedding_local_device': ('embedding', 'local_device'),
            'embedding_local_gguf_model_path': ('embedding', 'local_gguf_model_path'),
            'embedding_local_gguf_n_ctx': ('embedding', 'local_gguf_n_ctx'),
            'embedding_local_gguf_n_threads': ('embedding', 'local_gguf_n_threads'),
            'embedding_local_gguf_n_gpu_layers': ('embedding', 'local_gguf_n_gpu_layers'),
            'embedding_local_gguf_normalize': ('embedding', 'local_gguf_normalize'),
            'embedding_batch_size': ('embedding', 'batch_size'),
            'embedding_batch_delay_seconds': ('embedding', 'batch_delay_seconds'),
            'embedding_batch_max_retries': ('embedding', 'batch_max_retries'),
            'chunk_size': ('chunking', 'chunk_size'),
            'chunk_overlap': ('chunking', 'chunk_overlap'),
            'retrieval_mode': ('retrieval', 'retrieval_mode'),
            'top_k': ('retrieval', 'top_k'),
            'score_threshold': ('retrieval', 'score_threshold'),
            'recall_k': ('retrieval', 'recall_k'),
            'vector_recall_k': ('retrieval', 'vector_recall_k'),
            'bm25_recall_k': ('retrieval', 'bm25_recall_k'),
            'bm25_min_term_coverage': ('retrieval', 'bm25_min_term_coverage'),
            'fusion_top_k': ('retrieval', 'fusion_top_k'),
            'fusion_strategy': ('retrieval', 'fusion_strategy'),
            'rrf_k': ('retrieval', 'rrf_k'),
            'vector_weight': ('retrieval', 'vector_weight'),
            'bm25_weight': ('retrieval', 'bm25_weight'),
            'max_per_doc': ('retrieval', 'max_per_doc'),
            'reorder_strategy': ('retrieval', 'reorder_strategy'),
            'context_neighbor_window': ('retrieval', 'context_neighbor_window'),
            'context_neighbor_max_total': ('retrieval', 'context_neighbor_max_total'),
            'context_neighbor_dedup_coverage': ('retrieval', 'context_neighbor_dedup_coverage'),
            'retrieval_query_planner_enabled': ('retrieval', 'retrieval_query_planner_enabled'),
            'retrieval_query_planner_model_id': ('retrieval', 'retrieval_query_planner_model_id'),
            'retrieval_query_planner_max_queries': ('retrieval', 'retrieval_query_planner_max_queries'),
            'retrieval_query_planner_timeout_seconds': ('retrieval', 'retrieval_query_planner_timeout_seconds'),
            'structured_source_context_enabled': ('retrieval', 'structured_source_context_enabled'),
            'query_transform_enabled': ('retrieval', 'query_transform_enabled'),
            'query_transform_mode': ('retrieval', 'query_transform_mode'),
            'query_transform_model_id': ('retrieval', 'query_transform_model_id'),
            'query_transform_timeout_seconds': ('retrieval', 'query_transform_timeout_seconds'),
            'query_transform_guard_enabled': ('retrieval', 'query_transform_guard_enabled'),
            'query_transform_guard_max_new_terms': ('retrieval', 'query_transform_guard_max_new_terms'),
            'query_transform_crag_enabled': ('retrieval', 'query_transform_crag_enabled'),
            'query_transform_crag_lower_threshold': ('retrieval', 'query_transform_crag_lower_threshold'),
            'query_transform_crag_upper_threshold': ('retrieval', 'query_transform_crag_upper_threshold'),
            'rerank_enabled': ('retrieval', 'rerank_enabled'),
            'rerank_api_model': ('retrieval', 'rerank_api_model'),
            'rerank_api_base_url': ('retrieval', 'rerank_api_base_url'),
            'rerank_api_key': ('retrieval', 'rerank_api_key'),
            'rerank_timeout_seconds': ('retrieval', 'rerank_timeout_seconds'),
            'rerank_weight': ('retrieval', 'rerank_weight'),
            'vector_store_backend': ('storage', 'vector_store_backend'),
            'vector_sqlite_path': ('storage', 'vector_sqlite_path'),
            'persist_directory': ('storage', 'persist_directory'),
            'bm25_sqlite_path': ('storage', 'bm25_sqlite_path'),
        }

        for flat_key, value in flat_updates.items():
            if flat_key in mapping and value is not None:
                section, key = mapping[flat_key]
                if section not in nested:
                    nested[section] = {}
                nested[section][key] = value

        if nested:
            self.save_config(nested)
