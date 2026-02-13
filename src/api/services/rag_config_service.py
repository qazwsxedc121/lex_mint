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
    top_k: int = 5
    score_threshold: float = 0.3


@dataclass
class StorageConfig:
    persist_directory: str = "data/chromadb"


@dataclass
class RagConfig:
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)


class RagConfigService:
    """Service for managing RAG configuration"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = data_state_dir() / "rag_config.yaml"
        else:
            config_path = Path(config_path)

        self.config_path = config_path
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
                    'top_k': 5,
                    'score_threshold': 0.3,
                },
                'storage': {
                    'persist_directory': 'data/chromadb',
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
                    top_k=retrieval_data.get('top_k', 5),
                    score_threshold=retrieval_data.get('score_threshold', 0.3),
                ),
                storage=StorageConfig(
                    persist_directory=storage_data.get('persist_directory', 'data/chromadb'),
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
            'chunk_size': self.config.chunking.chunk_size,
            'chunk_overlap': self.config.chunking.chunk_overlap,
            'top_k': self.config.retrieval.top_k,
            'score_threshold': self.config.retrieval.score_threshold,
            'persist_directory': self.config.storage.persist_directory,
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
            'chunk_size': ('chunking', 'chunk_size'),
            'chunk_overlap': ('chunking', 'chunk_overlap'),
            'top_k': ('retrieval', 'top_k'),
            'score_threshold': ('retrieval', 'score_threshold'),
            'persist_directory': ('storage', 'persist_directory'),
        }

        for flat_key, value in flat_updates.items():
            if flat_key in mapping and value is not None:
                section, key = mapping[flat_key]
                if section not in nested:
                    nested[section] = {}
                nested[section][key] = value

        if nested:
            self.save_config(nested)
