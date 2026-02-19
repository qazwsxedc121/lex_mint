"""Dependency bootstrap helpers for AgentService."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .comparison_storage import ComparisonStorage
from .file_service import FileService
from .file_reference_config_service import FileReferenceConfigService
from .group_orchestration import CommitteePolicy
from .memory_service import MemoryService
from .pricing_service import PricingService
from .rag_config_service import RagConfigService
from .search_service import SearchService
from .source_context_service import SourceContextService
from .webpage_service import WebpageService
from ..config import settings

if TYPE_CHECKING:
    from .agent_service_simple import AgentService
    from .conversation_storage import ConversationStorage


def bootstrap_agent_service(service: "AgentService", storage: "ConversationStorage") -> None:
    """Initialize AgentService dependencies in one place.

    Keeping wiring here avoids repeated merge conflicts in AgentService when
    new services are introduced.
    """
    service.storage = storage
    service.pricing_service = PricingService()
    service.file_service = FileService(settings.attachments_dir, settings.max_file_size_mb)
    service.search_service = SearchService()
    service.webpage_service = WebpageService()
    service.memory_service = MemoryService()
    service.file_reference_config_service = FileReferenceConfigService()
    service.rag_config_service = RagConfigService()
    service.source_context_service = SourceContextService()
    service.comparison_storage = ComparisonStorage(service.storage)
    service._committee_policy = CommitteePolicy()
    service._committee_turn_executor = service._create_committee_turn_executor()
