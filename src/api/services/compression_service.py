"""Compression service for summarizing conversation context."""

import logging
import re
import time
from typing import AsyncIterator, Union, Dict, Any, Optional, Tuple, List, Sequence

from src.api.services.conversation_storage import ConversationStorage
from src.api.services.model_config_service import ModelConfigService
from src.api.services.compression_config_service import CompressionConfigService
from src.api.services.local_llama_cpp_service import LocalLlamaCppService
from src.api.services.language_detection_service import LanguageDetectionService
from src.api.services.think_tag_filter import strip_think_blocks
from src.agents.simple_llm import _filter_messages_by_context_boundary
from src.providers.types import CallMode

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4
_DEFAULT_MAX_HIERARCHY_LEVELS = 4
_MIN_CHUNK_TARGET_TOKENS = 192
_MIN_REDUCE_TARGET_TOKENS = 256
_DEFAULT_QUALITY_MIN_COVERAGE = 0.75
_DEFAULT_QUALITY_MAX_FACTS = 24
_DEFAULT_QUALITY_REPAIR_LIMIT = 10

_FACT_PATTERNS = (
    re.compile(r"https?://[^\s<>()]+"),
    re.compile(r"[A-Za-z]:\\[^\s<>()]+"),
    re.compile(r"(?:\./|\../|/)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+){1,}"),
    re.compile(r"\b[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+\b"),
    re.compile(r"`[^`\n]{2,120}`"),
)
_SAME_AS_CHAT_MODEL = "same_as_chat"

_OUTPUT_LANGUAGE_NAMES = {
    "zh": "Chinese",
    "en": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "pt": "Portuguese",
}

_REDUCE_INSTRUCTIONS = """You are merging multiple partial conversation summaries into one final compressed summary.

Additional merge requirements:
- Preserve critical technical details exactly: numbers, identifiers, file paths, commands, versions, constraints.
- Deduplicate repeated points.
- Keep the output concise and continuation-friendly.
- Keep the same language as the input summaries.
- If two summaries conflict, keep the latest statement and explicitly note the conflict briefly.
- Keep the output format consistent with the normal compression output format."""

_QUALITY_GUARD_REPAIR_TEMPLATE = """You are fixing a compressed conversation summary.

Rules:
- Keep the same language as the current summary.
- Preserve structure and keep it concise.
- Do not invent facts.
- Ensure each required fact appears exactly as written.
{language_instruction}

Current summary:
{summary}

Required facts:
{required_facts}

Return only the revised summary."""


class CompressionService:
    """Service for compressing conversation context via LLM summarization."""

    def __init__(self, storage: ConversationStorage):
        self.storage = storage
        self.config_service = CompressionConfigService()

    @staticmethod
    def _resolve_effective_compression_model_id(
        *,
        session_model_id: Optional[str],
        compression_model_id: Optional[str],
        provider: str,
    ) -> Optional[str]:
        if provider != "model_config":
            return session_model_id

        candidate = (compression_model_id or "").strip()
        if not candidate or candidate.lower() == _SAME_AS_CHAT_MODEL:
            return session_model_id
        return candidate

    @staticmethod
    def _estimate_text_tokens(text: str) -> int:
        content = text or ""
        return max(1, len(content) // _CHARS_PER_TOKEN)

    @classmethod
    def _estimate_message_tokens(cls, message: Dict[str, Any]) -> int:
        # Add a small per-message overhead to account for role wrappers.
        return cls._estimate_text_tokens(str(message.get("content", ""))) + 8

    @classmethod
    def _estimate_messages_tokens(cls, messages: Sequence[Dict[str, Any]]) -> int:
        return sum(cls._estimate_message_tokens(msg) for msg in messages)

    @staticmethod
    def _only_chat_messages(messages: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [msg for msg in messages if msg.get("role") in ("user", "assistant")]

    @classmethod
    def _chunk_messages(
        cls,
        messages: Sequence[Dict[str, Any]],
        *,
        target_tokens: int,
        overlap_messages: int,
    ) -> List[List[Dict[str, Any]]]:
        if not messages:
            return []

        safe_target = max(1, int(target_tokens))
        safe_overlap = max(0, int(overlap_messages))
        chunks: List[List[Dict[str, Any]]] = []
        i = 0
        total = len(messages)

        while i < total:
            start = i
            chunk: List[Dict[str, Any]] = []
            current_tokens = 0

            while i < total:
                msg = messages[i]
                msg_tokens = cls._estimate_message_tokens(msg)
                if chunk and current_tokens + msg_tokens > safe_target:
                    break
                chunk.append(msg)
                current_tokens += msg_tokens
                i += 1

            if not chunk:
                chunk = [messages[i]]
                i += 1

            chunks.append(chunk)
            if i >= total:
                break

            # Ensure progress even when overlap is larger than chunk length.
            i = max(i - safe_overlap, start + 1)

        return chunks

    @classmethod
    def _chunk_texts(
        cls,
        texts: Sequence[str],
        *,
        target_tokens: int,
        overlap_items: int,
    ) -> List[List[str]]:
        if not texts:
            return []

        safe_target = max(1, int(target_tokens))
        safe_overlap = max(0, int(overlap_items))
        chunks: List[List[str]] = []
        i = 0
        total = len(texts)

        while i < total:
            start = i
            chunk: List[str] = []
            current_tokens = 0

            while i < total:
                text = texts[i]
                text_tokens = cls._estimate_text_tokens(text) + 8
                if chunk and current_tokens + text_tokens > safe_target:
                    break
                chunk.append(text)
                current_tokens += text_tokens
                i += 1

            if not chunk:
                chunk = [texts[i]]
                i += 1

            chunks.append(chunk)
            if i >= total:
                break

            i = max(i - safe_overlap, start + 1)

        return chunks

    @classmethod
    def _build_reduce_prompt(
        cls,
        config: Any,
        partial_summaries: Sequence[str],
        *,
        output_language_code: Optional[str],
    ) -> str:
        serialized = "\n\n".join(
            f"[Summary {idx}]\n{text.strip()}"
            for idx, text in enumerate(partial_summaries, start=1)
            if (text or "").strip()
        )
        merged_input = (
            "<partial_summaries>\n"
            + (serialized or "[empty]")
            + "\n</partial_summaries>"
        )
        base_prompt = cls._build_compression_prompt(
            config,
            merged_input,
            output_language_code=output_language_code,
        )
        return (
            f"{_REDUCE_INSTRUCTIONS}\n\n"
            f"{base_prompt}\n\n"
            "Output only the merged summary."
        )

    @staticmethod
    def _local_input_budget_tokens(config: Any) -> int:
        # Keep a conservative prompt budget for local models.
        return max(512, int(int(config.local_gguf_n_ctx) * 0.7))

    @staticmethod
    def _local_chunk_target_tokens(config: Any) -> int:
        configured = int(getattr(config, "hierarchical_chunk_target_tokens", 0) or 0)
        if configured > 0:
            return max(_MIN_CHUNK_TARGET_TOKENS, configured)
        return max(
            _MIN_CHUNK_TARGET_TOKENS,
            min(2048, int(int(config.local_gguf_n_ctx) * 0.35)),
        )

    @staticmethod
    def _local_reduce_target_tokens(config: Any) -> int:
        configured = int(getattr(config, "hierarchical_reduce_target_tokens", 0) or 0)
        if configured > 0:
            return max(_MIN_REDUCE_TARGET_TOKENS, configured)
        return max(
            _MIN_REDUCE_TARGET_TOKENS,
            min(3072, int(int(config.local_gguf_n_ctx) * 0.45)),
        )

    @staticmethod
    def _local_chunk_overlap_messages(config: Any) -> int:
        return max(0, int(getattr(config, "hierarchical_chunk_overlap_messages", 2) or 0))

    @staticmethod
    def _local_reduce_overlap_items(config: Any) -> int:
        return max(0, int(getattr(config, "hierarchical_reduce_overlap_items", 1) or 0))

    @staticmethod
    def _local_max_hierarchy_levels(config: Any) -> int:
        return max(1, int(getattr(config, "hierarchical_max_levels", _DEFAULT_MAX_HIERARCHY_LEVELS) or 1))

    @staticmethod
    def _local_map_max_tokens(config: Any) -> int:
        return max(128, min(int(config.local_gguf_max_tokens), 1024))

    @staticmethod
    def _local_reduce_max_tokens(config: Any) -> int:
        return max(128, int(config.local_gguf_max_tokens))

    @staticmethod
    def _model_input_budget_tokens(context_length_tokens: int) -> int:
        return max(512, int(int(context_length_tokens) * 0.7))

    @staticmethod
    def _model_chunk_target_tokens(context_length_tokens: int, config: Any) -> int:
        configured = int(getattr(config, "hierarchical_chunk_target_tokens", 0) or 0)
        if configured > 0:
            return max(_MIN_CHUNK_TARGET_TOKENS, configured)
        return max(_MIN_CHUNK_TARGET_TOKENS, min(2048, int(int(context_length_tokens) * 0.35)))

    @staticmethod
    def _model_reduce_target_tokens(context_length_tokens: int, config: Any) -> int:
        configured = int(getattr(config, "hierarchical_reduce_target_tokens", 0) or 0)
        if configured > 0:
            return max(_MIN_REDUCE_TARGET_TOKENS, configured)
        return max(_MIN_REDUCE_TARGET_TOKENS, min(3072, int(int(context_length_tokens) * 0.45)))

    @staticmethod
    def _model_map_max_tokens(context_length_tokens: int) -> int:
        return max(192, min(1024, int(int(context_length_tokens) * 0.18)))

    @staticmethod
    def _model_reduce_max_tokens(context_length_tokens: int) -> int:
        return max(256, min(2048, int(int(context_length_tokens) * 0.24)))

    @staticmethod
    def _resolve_context_length_tokens(model_service: ModelConfigService, model_config: Any, provider_config: Any) -> int:
        merged = model_service.get_merged_capabilities(model_config, provider_config)
        return max(512, int(getattr(merged, "context_length", 4096) or 4096))

    @staticmethod
    def _quality_guard_enabled(config: Any) -> bool:
        return bool(getattr(config, "quality_guard_enabled", True))

    @staticmethod
    def _quality_guard_min_coverage(config: Any) -> float:
        value = float(getattr(config, "quality_guard_min_coverage", _DEFAULT_QUALITY_MIN_COVERAGE) or 0)
        return min(1.0, max(0.5, value))

    @staticmethod
    def _quality_guard_max_facts(config: Any) -> int:
        value = int(getattr(config, "quality_guard_max_facts", _DEFAULT_QUALITY_MAX_FACTS) or 0)
        return max(5, min(100, value))

    @staticmethod
    def _compression_metrics_enabled(config: Any) -> bool:
        return bool(getattr(config, "compression_metrics_enabled", True))

    @staticmethod
    def _compression_output_language_mode(config: Any) -> str:
        mode = str(getattr(config, "compression_output_language", "auto") or "auto").strip().lower()
        return mode or "auto"

    @staticmethod
    def _output_language_name(language_code: Optional[str]) -> Optional[str]:
        if not language_code:
            return None
        return _OUTPUT_LANGUAGE_NAMES.get(language_code.lower(), language_code)

    @classmethod
    def _build_output_language_instruction(cls, language_code: Optional[str]) -> str:
        if not language_code:
            return ""
        language_name = cls._output_language_name(language_code)
        return (
            "Output language requirement:\n"
            f"- Write all narrative summary text in {language_name}.\n"
            "- Keep technical terms, file paths, commands, identifiers, and code unchanged."
        )

    @classmethod
    def _resolve_output_language_for_messages(
        cls,
        messages: Sequence[Dict[str, Any]],
        config: Any,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        mode = cls._compression_output_language_mode(config)
        if mode == "none":
            return None, {"mode": mode, "detected_language": None, "detector": "none", "confidence": None}

        if mode == "auto":
            text = "\n".join(
                str(msg.get("content", ""))
                for msg in cls._only_chat_messages(messages)
                if str(msg.get("content", "")).strip()
            )
            detected_raw, confidence, detector = LanguageDetectionService.detect_language(text)
            detected = LanguageDetectionService.normalize_language_hint(detected_raw) or detected_raw
            effective = detected.lower() if detected else None
            return effective, {
                "mode": mode,
                "detected_language": detected_raw,
                "effective_language": effective,
                "detector": detector,
                "confidence": confidence,
            }

        normalized = LanguageDetectionService.normalize_language_hint(mode) or mode
        effective = normalized.lower()
        return effective, {
            "mode": mode,
            "detected_language": None,
            "effective_language": effective,
            "detector": "configured",
            "confidence": None,
        }

    @classmethod
    def _build_compression_prompt(
        cls,
        config: Any,
        formatted_messages: str,
        *,
        output_language_code: Optional[str],
    ) -> str:
        base_prompt = config.prompt_template.format(formatted_messages=formatted_messages)
        language_instruction = cls._build_output_language_instruction(output_language_code)
        if not language_instruction:
            return base_prompt
        return f"{language_instruction}\n\n{base_prompt}"

    @staticmethod
    def _normalize_fact(text: str) -> str:
        value = (text or "").strip().strip("`")
        value = value.strip(".,;:!?()[]{}<>\"'")
        return value

    @classmethod
    def _extract_critical_facts(
        cls,
        messages: Sequence[Dict[str, Any]],
        *,
        max_facts: int,
    ) -> List[str]:
        facts: List[str] = []
        seen: set[str] = set()
        safe_max = max(1, int(max_facts))

        for msg in messages:
            content = str(msg.get("content", "") or "")
            if not content:
                continue
            for pattern in _FACT_PATTERNS:
                for match in pattern.finditer(content):
                    fact = cls._normalize_fact(match.group(0))
                    if len(fact) < 3 or len(fact) > 160:
                        continue
                    key = fact.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    facts.append(fact)
                    if len(facts) >= safe_max:
                        return facts

        return facts

    @staticmethod
    def _critical_fact_coverage(summary: str, facts: Sequence[str]) -> Tuple[float, List[str]]:
        if not facts:
            return 1.0, []

        summary_lower = (summary or "").lower()
        missing = [fact for fact in facts if fact.lower() not in summary_lower]
        coverage = float((len(facts) - len(missing)) / len(facts))
        return coverage, missing

    @staticmethod
    def _build_quality_repair_prompt(
        summary: str,
        missing_facts: Sequence[str],
        *,
        language_instruction: str = "",
    ) -> str:
        required = "\n".join(f"- {fact}" for fact in missing_facts) or "- [none]"
        return _QUALITY_GUARD_REPAIR_TEMPLATE.format(
            summary=(summary or "").strip(),
            required_facts=required,
            language_instruction=language_instruction,
        )

    @staticmethod
    def _append_missing_facts(summary: str, missing_facts: Sequence[str]) -> str:
        if not missing_facts:
            return summary
        lines = "\n".join(f"- {fact}" for fact in missing_facts)
        return (summary or "").rstrip() + "\n\n### Critical Facts\n" + lines

    def _run_local_quality_guard(
        self,
        *,
        local_llm: LocalLlamaCppService,
        config: Any,
        source_messages: Sequence[Dict[str, Any]],
        summary: str,
        max_tokens: int,
        output_language_code: Optional[str],
    ) -> Tuple[str, Dict[str, Any]]:
        if not self._quality_guard_enabled(config):
            return summary, {"enabled": False}

        facts = self._extract_critical_facts(
            source_messages,
            max_facts=self._quality_guard_max_facts(config),
        )
        min_coverage = self._quality_guard_min_coverage(config)
        coverage_before, missing_before = self._critical_fact_coverage(summary, facts)
        guard_meta: Dict[str, Any] = {
            "enabled": True,
            "min_coverage": round(min_coverage, 3),
            "fact_count": len(facts),
            "coverage_before": round(coverage_before, 3),
            "missing_before_count": len(missing_before),
            "missing_before_sample": missing_before[:5],
            "repaired": False,
            "fallback_injected": False,
        }

        if not facts or coverage_before >= min_coverage:
            guard_meta["coverage_after"] = round(coverage_before, 3)
            guard_meta["missing_after_count"] = len(missing_before)
            guard_meta["missing_after_sample"] = missing_before[:5]
            guard_meta["passed"] = coverage_before >= min_coverage
            return summary, guard_meta

        missing_prompt = missing_before[:_DEFAULT_QUALITY_REPAIR_LIMIT]
        try:
            prompt = self._build_quality_repair_prompt(
                summary,
                missing_prompt,
                language_instruction=self._build_output_language_instruction(output_language_code),
            )
            repaired = local_llm.complete_prompt(
                prompt,
                temperature=min(0.2, float(config.temperature)),
                max_tokens=max_tokens,
            )
            repaired = strip_think_blocks(repaired).strip()
            if repaired:
                summary = repaired
                guard_meta["repaired"] = True
        except Exception as e:
            logger.warning("[COMPRESS][QUALITY] Repair pass failed: %s", e)

        coverage_after, missing_after = self._critical_fact_coverage(summary, facts)
        if missing_after and coverage_after < min_coverage:
            summary = self._append_missing_facts(summary, missing_after[:_DEFAULT_QUALITY_REPAIR_LIMIT])
            guard_meta["fallback_injected"] = True
            coverage_after, missing_after = self._critical_fact_coverage(summary, facts)

        guard_meta["coverage_after"] = round(coverage_after, 3)
        guard_meta["missing_after_count"] = len(missing_after)
        guard_meta["missing_after_sample"] = missing_after[:5]
        guard_meta["passed"] = coverage_after >= min_coverage
        return summary, guard_meta

    def _build_compression_metrics(
        self,
        *,
        started_at: float,
        input_tokens: int,
        output_text: str,
        mode: str,
        levels: int,
        initial_chunks: int,
    ) -> Dict[str, Any]:
        output_tokens = self._estimate_text_tokens(output_text or "")
        safe_input = max(1, int(input_tokens))
        ratio = float(output_tokens / safe_input)
        reduction = float(1.0 - ratio)
        return {
            "mode": mode,
            "levels": levels,
            "initial_chunks": initial_chunks,
            "estimated_input_tokens": int(input_tokens),
            "estimated_output_tokens": int(output_tokens),
            "estimated_compression_ratio": round(ratio, 3),
            "estimated_reduction_ratio": round(reduction, 3),
            "duration_ms": int((time.perf_counter() - started_at) * 1000),
        }

    def _summarize_message_chunk_with_local(
        self,
        *,
        local_llm: LocalLlamaCppService,
        config: Any,
        messages: Sequence[Dict[str, Any]],
        max_tokens: int,
        output_language_code: Optional[str],
    ) -> str:
        formatted = self._format_messages(messages)
        prompt = self._build_compression_prompt(
            config,
            formatted,
            output_language_code=output_language_code,
        )
        summary = local_llm.complete_prompt(
            prompt,
            temperature=config.temperature,
            max_tokens=max_tokens,
        )
        return strip_think_blocks(summary).strip()

    def _summarize_text_group_with_local(
        self,
        *,
        local_llm: LocalLlamaCppService,
        config: Any,
        summaries: Sequence[str],
        max_tokens: int,
        output_language_code: Optional[str],
    ) -> str:
        prompt = self._build_reduce_prompt(
            config,
            summaries,
            output_language_code=output_language_code,
        )
        merged = local_llm.complete_prompt(
            prompt,
            temperature=config.temperature,
            max_tokens=max_tokens,
        )
        return strip_think_blocks(merged).strip()

    def _compress_with_local_gguf(
        self,
        *,
        local_llm: LocalLlamaCppService,
        config: Any,
        compressible: Sequence[Dict[str, Any]],
        output_language_code: Optional[str] = None,
        output_language_meta: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        started_at = time.perf_counter()
        chat_messages = self._only_chat_messages(compressible)
        if not chat_messages:
            return "", {"mode": "empty", "levels": 0, "initial_chunks": 0}
        if output_language_meta is None:
            resolved_code, resolved_meta = self._resolve_output_language_for_messages(chat_messages, config)
            output_language_code = output_language_code or resolved_code
            output_language_meta = resolved_meta
        elif output_language_code is None:
            output_language_code = output_language_meta.get("effective_language")

        budget_tokens = self._local_input_budget_tokens(config)
        total_tokens = self._estimate_messages_tokens(chat_messages)
        map_max_tokens = self._local_map_max_tokens(config)
        reduce_max_tokens = self._local_reduce_max_tokens(config)
        mode = "single_pass"
        levels = 1
        initial_chunks = 1
        summary = ""
        quality_meta: Dict[str, Any] = {"enabled": False}

        # Path selection is based on context budget only:
        # fit-in-budget -> single pass; overflow -> hierarchical map/reduce.
        if total_tokens <= budget_tokens:
            mode = "single_pass"
            summary = self._summarize_message_chunk_with_local(
                local_llm=local_llm,
                config=config,
                messages=chat_messages,
                max_tokens=reduce_max_tokens,
                output_language_code=output_language_code,
            )
        else:
            mode = "hierarchical"
            message_chunks = self._chunk_messages(
                chat_messages,
                target_tokens=self._local_chunk_target_tokens(config),
                overlap_messages=self._local_chunk_overlap_messages(config),
            )
            initial_chunks = len(message_chunks)
            level_summaries: List[str] = []
            for chunk in message_chunks:
                chunk_summary = self._summarize_message_chunk_with_local(
                    local_llm=local_llm,
                    config=config,
                    messages=chunk,
                    max_tokens=map_max_tokens,
                    output_language_code=output_language_code,
                )
                if chunk_summary:
                    level_summaries.append(chunk_summary)

            if not level_summaries:
                return "", {"mode": "hierarchical_failed", "levels": 1, "initial_chunks": len(message_chunks)}

            levels = 1
            max_levels = self._local_max_hierarchy_levels(config)
            reduce_target_tokens = self._local_reduce_target_tokens(config)

            while len(level_summaries) > 1:
                levels += 1
                grouped = self._chunk_texts(
                    level_summaries,
                    target_tokens=reduce_target_tokens,
                    overlap_items=self._local_reduce_overlap_items(config),
                )
                reduced_summaries: List[str] = []
                for group in grouped:
                    merged = self._summarize_text_group_with_local(
                        local_llm=local_llm,
                        config=config,
                        summaries=group,
                        max_tokens=reduce_max_tokens,
                        output_language_code=output_language_code,
                    )
                    if merged:
                        reduced_summaries.append(merged)

                if not reduced_summaries:
                    break

                level_summaries = reduced_summaries
                if levels >= max_levels and len(level_summaries) > 1:
                    # Hard stop to avoid endless reductions; force-merge remaining summaries.
                    forced = self._summarize_text_group_with_local(
                        local_llm=local_llm,
                        config=config,
                        summaries=level_summaries,
                        max_tokens=reduce_max_tokens,
                        output_language_code=output_language_code,
                    )
                    level_summaries = [forced] if forced else level_summaries[:1]
                    break

            summary = (level_summaries[0] if level_summaries else "").strip()

        if summary and self._quality_guard_enabled(config):
            summary, quality_meta = self._run_local_quality_guard(
                local_llm=local_llm,
                config=config,
                source_messages=chat_messages,
                summary=summary,
                max_tokens=reduce_max_tokens,
                output_language_code=output_language_code,
            )

        meta = {
            "mode": mode,
            "levels": levels,
            "initial_chunks": initial_chunks,
            "estimated_tokens": total_tokens,
            "budget_tokens": budget_tokens,
            "path_selector": "context_budget",
        }
        meta["output_language"] = output_language_meta
        if self._compression_metrics_enabled(config):
            meta["metrics"] = self._build_compression_metrics(
                started_at=started_at,
                input_tokens=total_tokens,
                output_text=summary,
                mode=mode,
                levels=levels,
                initial_chunks=initial_chunks,
            )
        meta["quality_guard"] = quality_meta
        return summary, meta

    async def _summarize_message_chunk_with_adapter(
        self,
        *,
        adapter: Any,
        llm: Any,
        config: Any,
        messages: Sequence[Dict[str, Any]],
        output_language_code: Optional[str],
        allow_responses_fallback: bool = False,
    ) -> str:
        from langchain_core.messages import HumanMessage as HMsg

        formatted = self._format_messages(messages)
        prompt = self._build_compression_prompt(
            config,
            formatted,
            output_language_code=output_language_code,
        )
        invoke_kwargs = {"allow_responses_fallback": True} if allow_responses_fallback else {}
        response = await adapter.invoke(llm, [HMsg(content=prompt)], **invoke_kwargs)
        return strip_think_blocks(getattr(response, "content", "") or "").strip()

    async def _summarize_text_group_with_adapter(
        self,
        *,
        adapter: Any,
        llm: Any,
        config: Any,
        summaries: Sequence[str],
        output_language_code: Optional[str],
        allow_responses_fallback: bool = False,
    ) -> str:
        from langchain_core.messages import HumanMessage as HMsg

        prompt = self._build_reduce_prompt(
            config,
            summaries,
            output_language_code=output_language_code,
        )
        invoke_kwargs = {"allow_responses_fallback": True} if allow_responses_fallback else {}
        response = await adapter.invoke(llm, [HMsg(content=prompt)], **invoke_kwargs)
        return strip_think_blocks(getattr(response, "content", "") or "").strip()

    async def _compress_with_model_config(
        self,
        *,
        adapter: Any,
        llm_factory: Any,
        config: Any,
        compressible: Sequence[Dict[str, Any]],
        context_length_tokens: int,
        output_language_code: Optional[str],
        output_language_meta: Dict[str, Any],
        allow_responses_fallback: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        started_at = time.perf_counter()
        chat_messages = self._only_chat_messages(compressible)
        if not chat_messages:
            return "", {"mode": "empty", "levels": 0, "initial_chunks": 0}

        budget_tokens = self._model_input_budget_tokens(context_length_tokens)
        total_tokens = self._estimate_messages_tokens(chat_messages)
        map_max_tokens = self._model_map_max_tokens(context_length_tokens)
        reduce_max_tokens = self._model_reduce_max_tokens(context_length_tokens)
        mode = "single_pass"
        levels = 1
        initial_chunks = 1
        summary = ""

        if total_tokens <= budget_tokens:
            llm = llm_factory(max_tokens=reduce_max_tokens)
            summary = await self._summarize_message_chunk_with_adapter(
                adapter=adapter,
                llm=llm,
                config=config,
                messages=chat_messages,
                output_language_code=output_language_code,
                allow_responses_fallback=allow_responses_fallback,
            )
        else:
            mode = "hierarchical"
            message_chunks = self._chunk_messages(
                chat_messages,
                target_tokens=self._model_chunk_target_tokens(context_length_tokens, config),
                overlap_messages=self._local_chunk_overlap_messages(config),
            )
            initial_chunks = len(message_chunks)
            level_summaries: List[str] = []
            for chunk in message_chunks:
                llm = llm_factory(max_tokens=map_max_tokens)
                chunk_summary = await self._summarize_message_chunk_with_adapter(
                    adapter=adapter,
                    llm=llm,
                    config=config,
                    messages=chunk,
                    output_language_code=output_language_code,
                    allow_responses_fallback=allow_responses_fallback,
                )
                if chunk_summary:
                    level_summaries.append(chunk_summary)

            if not level_summaries:
                return "", {"mode": "hierarchical_failed", "levels": 1, "initial_chunks": len(message_chunks)}

            levels = 1
            max_levels = self._local_max_hierarchy_levels(config)
            reduce_target_tokens = self._model_reduce_target_tokens(context_length_tokens, config)

            while len(level_summaries) > 1:
                levels += 1
                grouped = self._chunk_texts(
                    level_summaries,
                    target_tokens=reduce_target_tokens,
                    overlap_items=self._local_reduce_overlap_items(config),
                )
                reduced_summaries: List[str] = []
                for group in grouped:
                    llm = llm_factory(max_tokens=reduce_max_tokens)
                    merged = await self._summarize_text_group_with_adapter(
                        adapter=adapter,
                        llm=llm,
                        config=config,
                        summaries=group,
                        output_language_code=output_language_code,
                        allow_responses_fallback=allow_responses_fallback,
                    )
                    if merged:
                        reduced_summaries.append(merged)

                if not reduced_summaries:
                    break

                level_summaries = reduced_summaries
                if levels >= max_levels and len(level_summaries) > 1:
                    llm = llm_factory(max_tokens=reduce_max_tokens)
                    forced = await self._summarize_text_group_with_adapter(
                        adapter=adapter,
                        llm=llm,
                        config=config,
                        summaries=level_summaries,
                        output_language_code=output_language_code,
                        allow_responses_fallback=allow_responses_fallback,
                    )
                    level_summaries = [forced] if forced else level_summaries[:1]
                    break

            summary = (level_summaries[0] if level_summaries else "").strip()

        meta = {
            "mode": mode,
            "levels": levels,
            "initial_chunks": initial_chunks,
            "estimated_tokens": total_tokens,
            "budget_tokens": budget_tokens,
            "path_selector": "context_budget",
            "output_language": output_language_meta,
        }
        if self._compression_metrics_enabled(config):
            meta["metrics"] = self._build_compression_metrics(
                started_at=started_at,
                input_tokens=total_tokens,
                output_text=summary,
                mode=mode,
                levels=levels,
                initial_chunks=initial_chunks,
            )
        return summary, meta

    async def compress_context_stream(
        self,
        session_id: str,
        context_type: str = "chat",
        project_id: str = None,
    ) -> AsyncIterator[Union[str, Dict[str, Any]]]:
        """Compress conversation context by summarizing messages via LLM.

        Streams summary tokens, then appends the summary to storage.

        Args:
            session_id: Session UUID
            context_type: Context type ("chat" or "project")
            project_id: Project ID (optional)

        Yields:
            String tokens during streaming, or dict events at the end.
        """
        # Reload config to pick up latest changes
        self.config_service.reload_config()
        config = self.config_service.config

        # Load session
        session = await self.storage.get_session(
            session_id, context_type=context_type, project_id=project_id
        )
        messages = session["state"]["messages"]
        model_id = session.get("model_id")

        # Apply param overrides for model selection
        param_overrides = session.get("param_overrides", {})
        if param_overrides and "model_id" in param_overrides:
            model_id = param_overrides["model_id"]

        # Filter to get only the compressible messages (after last boundary)
        compressible, _ = _filter_messages_by_context_boundary(messages)

        # Check minimum messages
        if len(compressible) < config.min_messages:
            yield {"type": "error", "error": f"Not enough messages to compress (need at least {config.min_messages})"}
            return

        compressed_count = len(compressible)
        chat_messages = self._only_chat_messages(compressible)
        output_language_code, output_language_meta = self._resolve_output_language_for_messages(
            chat_messages,
            config,
        )

        # Use compression-specific model if configured, otherwise fall back to session model
        model_id = self._resolve_effective_compression_model_id(
            session_model_id=model_id,
            compression_model_id=config.model_id,
            provider=config.provider,
        )

        if config.provider == "local_gguf":
            try:
                local_llm = LocalLlamaCppService(
                    model_path=config.local_gguf_model_path,
                    n_ctx=config.local_gguf_n_ctx,
                    n_threads=config.local_gguf_n_threads,
                    n_gpu_layers=config.local_gguf_n_gpu_layers,
                )
            except Exception as e:
                yield {"type": "error", "error": str(e)}
                return

            actual_model_id = f"local_gguf:{local_llm.model_path.name}"
            print(f"[COMPRESS] Starting local GGUF compression (model: {actual_model_id})")
            print(f"[COMPRESS] Compressing {compressed_count} messages")
            logger.info(f"Local GGUF compression started: {compressed_count} messages, model: {actual_model_id}")

            try:
                full_response, compression_meta = self._compress_with_local_gguf(
                    local_llm=local_llm,
                    config=config,
                    compressible=compressible,
                    output_language_code=output_language_code,
                    output_language_meta=output_language_meta,
                )
                if not full_response:
                    raise RuntimeError("Compression produced empty summary.")
                if full_response:
                    yield full_response

                logger.info(
                    "[COMPRESS][LOCAL] mode=%s levels=%s initial_chunks=%s",
                    compression_meta.get("mode"),
                    compression_meta.get("levels"),
                    compression_meta.get("initial_chunks"),
                )
                logger.info("[COMPRESS][LOCAL] quality_guard=%s", compression_meta.get("quality_guard"))
                logger.info("[COMPRESS][LOCAL] metrics=%s", compression_meta.get("metrics"))
                message_id = await self.storage.append_summary(
                    session_id=session_id,
                    content=full_response,
                    compressed_count=compressed_count,
                    compression_meta=compression_meta,
                    context_type=context_type,
                    project_id=project_id,
                )
                print(f"[COMPRESS] Compression complete: {len(full_response)} chars, message_id: {message_id[:8]}...")
                logger.info(f"Context compression complete: {len(full_response)} chars")
                yield {
                    "type": "compression_complete",
                    "message_id": message_id,
                    "compressed_count": compressed_count,
                    "compression_meta": compression_meta,
                }
                return
            except Exception as e:
                print(f"[ERROR] Compression failed: {str(e)}")
                logger.error(f"Compression failed: {str(e)}", exc_info=True)
                yield {"type": "error", "error": str(e)}
                return

        # Get model and adapter
        model_service = ModelConfigService()
        model_config, provider_config = model_service.get_model_and_provider_sync(model_id)

        adapter = model_service.get_adapter_for_provider(provider_config)
        resolved_call_mode = model_service.resolve_effective_call_mode(provider_config)
        effective_call_mode = (
            resolved_call_mode
            if isinstance(resolved_call_mode, CallMode)
            else CallMode.AUTO
        )
        allow_responses_fallback = effective_call_mode == CallMode.RESPONSES

        try:
            api_key = model_service.resolve_provider_api_key_sync(provider_config)
        except RuntimeError as e:
            yield {"type": "error", "error": str(e)}
            return

        context_length_tokens = self._resolve_context_length_tokens(
            model_service,
            model_config,
            provider_config,
        )

        actual_model_id = f"{provider_config.id}:{model_config.id}"
        print(
            f"[COMPRESS] Starting context compression "
            f"(model: {actual_model_id}, call_mode: {effective_call_mode.value})"
        )
        print(f"[COMPRESS] Compressing {compressed_count} messages")
        logger.info(
            "Context compression started: %s messages, model: %s, call_mode=%s, responses_fallback=%s",
            compressed_count,
            actual_model_id,
            effective_call_mode.value,
            allow_responses_fallback,
        )

        try:
            def llm_factory(*, max_tokens: int):
                return adapter.create_llm(
                    model=model_config.id,
                    base_url=provider_config.base_url,
                    api_key=api_key,
                    temperature=config.temperature,
                    streaming=False,
                    max_tokens=max_tokens,
                    call_mode=effective_call_mode.value,
                )

            full_response, stream_meta = await self._compress_with_model_config(
                adapter=adapter,
                llm_factory=llm_factory,
                config=config,
                compressible=compressible,
                context_length_tokens=context_length_tokens,
                output_language_code=output_language_code,
                output_language_meta=output_language_meta,
                allow_responses_fallback=allow_responses_fallback,
            )
            if not full_response:
                raise RuntimeError("Compression produced empty summary.")
            yield full_response

            logger.info(
                "[COMPRESS][MODEL] mode=%s levels=%s initial_chunks=%s",
                stream_meta.get("mode"),
                stream_meta.get("levels"),
                stream_meta.get("initial_chunks"),
            )
            logger.info("[COMPRESS][MODEL] metrics=%s", stream_meta.get("metrics"))
            message_id = await self.storage.append_summary(
                session_id=session_id,
                content=full_response,
                compressed_count=compressed_count,
                compression_meta=stream_meta,
                context_type=context_type,
                project_id=project_id,
            )

            print(f"[COMPRESS] Compression complete: {len(full_response)} chars, message_id: {message_id[:8]}...")
            logger.info(f"Context compression complete: {len(full_response)} chars")

            yield {
                "type": "compression_complete",
                "message_id": message_id,
                "compressed_count": compressed_count,
                "compression_meta": stream_meta,
            }

        except Exception as e:
            print(f"[ERROR] Compression failed: {str(e)}")
            logger.error(f"Compression failed: {str(e)}", exc_info=True)
            yield {"type": "error", "error": str(e)}

    def _format_messages(self, messages):
        """Format messages into XML structure for summarization."""
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role in ("user", "assistant"):
                parts.append(f"<{role}>{content}</{role}>")
        return "<chat_history>\n" + "\n".join(parts) + "\n</chat_history>"

    async def compress_context(
        self,
        session_id: str,
        context_type: str = "chat",
        project_id: str = None,
    ) -> Optional[Tuple[str, int]]:
        """Non-streaming compression for auto-trigger use.

        Args:
            session_id: Session UUID
            context_type: Context type ("chat" or "project")
            project_id: Project ID (optional)

        Returns:
            Tuple of (message_id, compressed_count) on success, None on failure.
        """
        self.config_service.reload_config()
        config = self.config_service.config

        # Load session
        session = await self.storage.get_session(
            session_id, context_type=context_type, project_id=project_id
        )
        messages = session["state"]["messages"]
        model_id = session.get("model_id")

        param_overrides = session.get("param_overrides", {})
        if param_overrides and "model_id" in param_overrides:
            model_id = param_overrides["model_id"]

        # Filter to get only compressible messages
        compressible, _ = _filter_messages_by_context_boundary(messages)

        if len(compressible) < config.min_messages:
            logger.info(f"[AUTO-COMPRESS] Skipped: only {len(compressible)} messages (need {config.min_messages})")
            return None

        compressed_count = len(compressible)
        chat_messages = self._only_chat_messages(compressible)
        output_language_code, output_language_meta = self._resolve_output_language_for_messages(
            chat_messages,
            config,
        )

        model_id = self._resolve_effective_compression_model_id(
            session_model_id=model_id,
            compression_model_id=config.model_id,
            provider=config.provider,
        )

        if config.provider == "local_gguf":
            try:
                local_llm = LocalLlamaCppService(
                    model_path=config.local_gguf_model_path,
                    n_ctx=config.local_gguf_n_ctx,
                    n_threads=config.local_gguf_n_threads,
                    n_gpu_layers=config.local_gguf_n_gpu_layers,
                )
                full_response, compression_meta = self._compress_with_local_gguf(
                    local_llm=local_llm,
                    config=config,
                    compressible=compressible,
                    output_language_code=output_language_code,
                    output_language_meta=output_language_meta,
                )
                if not full_response:
                    raise RuntimeError("Compression produced empty summary.")
                logger.info(
                    "[AUTO-COMPRESS][LOCAL] mode=%s levels=%s initial_chunks=%s",
                    compression_meta.get("mode"),
                    compression_meta.get("levels"),
                    compression_meta.get("initial_chunks"),
                )
                logger.info("[AUTO-COMPRESS][LOCAL] quality_guard=%s", compression_meta.get("quality_guard"))
                logger.info("[AUTO-COMPRESS][LOCAL] metrics=%s", compression_meta.get("metrics"))
                message_id = await self.storage.append_summary(
                    session_id=session_id,
                    content=full_response,
                    compressed_count=compressed_count,
                    compression_meta=compression_meta,
                    context_type=context_type,
                    project_id=project_id,
                )
                print(
                    f"[AUTO-COMPRESS] Complete: {len(full_response)} chars, "
                    f"message_id: {message_id[:8]}..."
                )
                logger.info(f"Auto-compression complete: {len(full_response)} chars")
                return message_id, compressed_count
            except Exception as e:
                print(f"[ERROR] Auto-compression failed: {str(e)}")
                logger.error(f"Auto-compression failed: {str(e)}", exc_info=True)
                return None

        model_service = ModelConfigService()
        model_config, provider_config = model_service.get_model_and_provider_sync(model_id)
        adapter = model_service.get_adapter_for_provider(provider_config)
        resolved_call_mode = model_service.resolve_effective_call_mode(provider_config)
        effective_call_mode = (
            resolved_call_mode
            if isinstance(resolved_call_mode, CallMode)
            else CallMode.AUTO
        )
        allow_responses_fallback = effective_call_mode == CallMode.RESPONSES

        try:
            api_key = model_service.resolve_provider_api_key_sync(provider_config)
        except RuntimeError as e:
            logger.error(f"[AUTO-COMPRESS] {e}")
            return None

        context_length_tokens = self._resolve_context_length_tokens(
            model_service,
            model_config,
            provider_config,
        )

        actual_model_id = f"{provider_config.id}:{model_config.id}"
        print(
            f"[AUTO-COMPRESS] Starting auto-compression "
            f"(model: {actual_model_id}, call_mode: {effective_call_mode.value}, {compressed_count} messages)"
        )
        logger.info(
            "Auto-compression started: %s messages, model: %s, call_mode=%s, responses_fallback=%s",
            compressed_count,
            actual_model_id,
            effective_call_mode.value,
            allow_responses_fallback,
        )

        try:
            def llm_factory(*, max_tokens: int):
                return adapter.create_llm(
                    model=model_config.id,
                    base_url=provider_config.base_url,
                    api_key=api_key,
                    temperature=config.temperature,
                    streaming=False,
                    max_tokens=max_tokens,
                    call_mode=effective_call_mode.value,
                )

            full_response, auto_meta = await self._compress_with_model_config(
                adapter=adapter,
                llm_factory=llm_factory,
                config=config,
                compressible=compressible,
                context_length_tokens=context_length_tokens,
                output_language_code=output_language_code,
                output_language_meta=output_language_meta,
                allow_responses_fallback=allow_responses_fallback,
            )
            if not full_response:
                raise RuntimeError("Compression produced empty summary.")
            logger.info(
                "[AUTO-COMPRESS][MODEL] mode=%s levels=%s initial_chunks=%s",
                auto_meta.get("mode"),
                auto_meta.get("levels"),
                auto_meta.get("initial_chunks"),
            )
            logger.info("[AUTO-COMPRESS][MODEL] metrics=%s", auto_meta.get("metrics"))
            message_id = await self.storage.append_summary(
                session_id=session_id,
                content=full_response,
                compressed_count=compressed_count,
                compression_meta=auto_meta,
                context_type=context_type,
                project_id=project_id,
            )

            print(f"[AUTO-COMPRESS] Complete: {len(full_response)} chars, message_id: {message_id[:8]}...")
            logger.info(f"Auto-compression complete: {len(full_response)} chars")
            return message_id, compressed_count

        except Exception as e:
            print(f"[ERROR] Auto-compression failed: {str(e)}")
            logger.error(f"Auto-compression failed: {str(e)}", exc_info=True)
            return None
