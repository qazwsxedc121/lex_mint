#!/usr/bin/env python3
"""Run a single-pass vs chunked-two-stage compression comparison.

This script:
1) Builds a synthetic long conversation.
2) Runs one-pass compression with the online model from compression config.
3) Runs chunked map + reduce compression with the same model.
4) Saves inputs, intermediate outputs, summaries, and metrics to data/benchmarks.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Sequence, Tuple
import time

from langchain_core.messages import HumanMessage

from src.api.services.compression_config_service import CompressionConfigService
from src.api.services.compression_service import CompressionService
from src.api.services.model_config_service import ModelConfigService
from src.providers.types import TokenUsage


@dataclass
class CallResult:
    content: str
    usage: Dict[str, int] | None
    prompt: str
    duration_ms: int


def _build_synthetic_conversation(rounds: int = 16) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []

    fixed_facts = [
        "Project root: /Users/xiaocanguo/GitHub/lex_mint",
        "Test command: ./venv/bin/python -m pytest",
        "Backend run command: ./venv/bin/uvicorn src.api.main:app --reload --port 8000",
        "Config endpoint: /api/compression/config",
        "Primary model: deepseek:deepseek-chat",
        "Critical file: src/api/services/compression_service.py",
        "Feature toggle: compression_strategy=hierarchical",
        "Safety rule: preserve file paths, commands, and numeric limits",
    ]

    for i in range(1, rounds + 1):
        user_msg = (
            f"Round {i} user request: We are preparing context compression changes for production. "
            f"Keep these facts stable: {fixed_facts[i % len(fixed_facts)]}. "
            f"Also include checkpoint id CP-{1000 + i}, timeout={45 + i}s, and retry_limit={2 + (i % 3)}. "
            "Please keep references to API routes, constraints, and command lines exact."
        )
        assistant_msg = (
            f"Round {i} assistant update: Completed analysis for module {i}. "
            f"Applied decision D-{2000 + i}: prioritize continuity, dedupe repeated constraints, "
            f"and keep sequence order across chunks. "
            f"Validation note: wrote report to docs/eval/run_{i:02d}.md and checked file src/api/routers/chat.py. "
            "Potential conflict: old threshold=0.6, new threshold=0.5, latest value should win."
        )
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})

    return messages


def _usage_to_dict(usage: TokenUsage | None) -> Dict[str, int] | None:
    if usage is None:
        return None
    return {
        "prompt_tokens": int(usage.prompt_tokens),
        "completion_tokens": int(usage.completion_tokens),
        "total_tokens": int(usage.total_tokens),
    }


def _sum_usage(usages: Sequence[Dict[str, int] | None]) -> Dict[str, int]:
    total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    for usage in usages:
        if not usage:
            continue
        total["prompt_tokens"] += int(usage.get("prompt_tokens", 0))
        total["completion_tokens"] += int(usage.get("completion_tokens", 0))
        total["total_tokens"] += int(usage.get("total_tokens", 0))
    return total


def _resolve_benchmark_model_id(config_model_id: str | None) -> str:
    candidate = (config_model_id or "").strip()
    if candidate and candidate != "same_as_chat":
        return candidate

    svc = ModelConfigService()
    model, provider = svc.get_model_and_provider_sync(None)
    return f"{provider.id}:{model.id}"


async def _invoke_online_model(
    *,
    model_service: ModelConfigService,
    model_id: str,
    temperature: float,
    timeout_seconds: int,
    prompt: str,
    max_tokens: int,
) -> CallResult:
    start = time.perf_counter()
    model, provider = model_service.get_model_and_provider_sync(model_id)
    adapter = model_service.get_adapter_for_provider(provider)
    api_key = model_service.resolve_provider_api_key_sync(provider)
    llm = adapter.create_llm(
        model=model.id,
        base_url=provider.base_url,
        api_key=api_key,
        temperature=temperature,
        streaming=False,
        timeout=float(timeout_seconds),
        max_tokens=int(max_tokens),
    )
    response = await adapter.invoke(llm, [HumanMessage(content=prompt)])
    return CallResult(
        content=(response.content or "").strip(),
        usage=_usage_to_dict(response.usage),
        prompt=prompt,
        duration_ms=int((time.perf_counter() - start) * 1000),
    )


def _build_report_markdown(
    *,
    model_id: str,
    chunk_count: int,
    single_tokens_in: int,
    single_tokens_out: int,
    two_tokens_out: int,
    single_cov: float,
    two_cov: float,
    single_usage: Dict[str, int] | None,
    two_usage: Dict[str, int],
    single_duration_ms: int,
    two_duration_ms: int,
    map_duration_ms: int,
    reduce_duration_ms: int,
) -> str:
    single_ratio = (single_tokens_out / max(1, single_tokens_in))
    two_ratio = (two_tokens_out / max(1, single_tokens_in))
    lines = [
        "# Compression Comparison Report",
        "",
        f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Model: `{model_id}`",
        "- Experiment: one-pass vs chunked map+reduce (two-stage)",
        "",
        "## Key Results",
        f"- Input estimated tokens: {single_tokens_in}",
        f"- One-pass output estimated tokens: {single_tokens_out} (ratio={single_ratio:.3f})",
        f"- Two-stage output estimated tokens: {two_tokens_out} (ratio={two_ratio:.3f})",
        f"- Chunk count (map stage): {chunk_count}",
        f"- Critical-fact coverage (one-pass): {single_cov:.3f}",
        f"- Critical-fact coverage (two-stage): {two_cov:.3f}",
        "",
        "## API Usage (provider reported)",
        f"- One-pass usage: {json.dumps(single_usage or {}, ensure_ascii=True)}",
        f"- Two-stage aggregate usage: {json.dumps(two_usage, ensure_ascii=True)}",
        "",
        "## Latency",
        f"- One-pass duration: {single_duration_ms} ms",
        f"- Two-stage duration (total): {two_duration_ms} ms",
        f"- Two-stage map duration (sum): {map_duration_ms} ms",
        f"- Two-stage reduce duration: {reduce_duration_ms} ms",
        "",
        "## Conclusion",
        "- If two-stage keeps similar or better fact coverage with acceptable token cost, the change is considered successful.",
        "- Check `single_pass_summary.md`, `two_stage_final_summary.md`, and `two_stage_intermediate.md` for qualitative review.",
    ]
    return "\n".join(lines) + "\n"


async def main() -> None:
    # Build conversation and helpers
    messages = _build_synthetic_conversation(rounds=16)
    compression_service = CompressionService(storage=SimpleNamespace())
    config = CompressionConfigService().config
    model_service = ModelConfigService()

    model_id = _resolve_benchmark_model_id(config.model_id)
    temperature = float(config.temperature)
    timeout_seconds = int(config.timeout_seconds)
    output_language_code, output_language_meta = compression_service._resolve_output_language_for_messages(
        messages,
        config,
    )

    # Force chunking for comparison (independent from runtime strategy).
    eval_chunk_target_tokens = 260
    eval_chunk_overlap_messages = 2
    eval_map_max_tokens = 500
    eval_reduce_max_tokens = 900

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model_id.replace(":", "_").replace("/", "_")
    out_dir = Path("data") / "benchmarks" / f"compression_compare_{timestamp}_{safe_model}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save input dataset
    (out_dir / "input_conversation.json").write_text(
        json.dumps({"messages": messages}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    config_snapshot = {
        "model_id": model_id,
        "temperature": temperature,
        "timeout_seconds": timeout_seconds,
        "compression_output_language_mode": getattr(config, "compression_output_language", "auto"),
        "resolved_output_language": output_language_code,
        "output_language_meta": output_language_meta,
        "prompt_template_preview": config.prompt_template[:320],
        "eval_chunk_target_tokens": eval_chunk_target_tokens,
        "eval_chunk_overlap_messages": eval_chunk_overlap_messages,
        "eval_map_max_tokens": eval_map_max_tokens,
        "eval_reduce_max_tokens": eval_reduce_max_tokens,
    }
    (out_dir / "config_snapshot.json").write_text(
        json.dumps(config_snapshot, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # One-pass compression
    formatted_full = compression_service._format_messages(messages)
    one_pass_prompt = compression_service._build_compression_prompt(
        config,
        formatted_full,
        output_language_code=output_language_code,
    )
    one_pass = await _invoke_online_model(
        model_service=model_service,
        model_id=model_id,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        prompt=one_pass_prompt,
        max_tokens=eval_reduce_max_tokens,
    )

    # Two-stage compression: map
    chunks = compression_service._chunk_messages(
        messages,
        target_tokens=eval_chunk_target_tokens,
        overlap_messages=eval_chunk_overlap_messages,
    )
    map_results: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, start=1):
        formatted_chunk = compression_service._format_messages(chunk)
        chunk_prompt = compression_service._build_compression_prompt(
            config,
            formatted_chunk,
            output_language_code=output_language_code,
        )
        chunk_result = await _invoke_online_model(
            model_service=model_service,
            model_id=model_id,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
            prompt=chunk_prompt,
            max_tokens=eval_map_max_tokens,
        )
        map_results.append(
            {
                "chunk_index": idx,
                "message_count": len(chunk),
                "estimated_input_tokens": compression_service._estimate_messages_tokens(chunk),
                "summary": chunk_result.content,
                "usage": chunk_result.usage,
                "duration_ms": int(chunk_result.duration_ms),
            }
        )

    map_summaries = [item["summary"] for item in map_results if item["summary"]]
    reduce_prompt = compression_service._build_reduce_prompt(
        config,
        map_summaries,
        output_language_code=output_language_code,
    )
    reduce_result = await _invoke_online_model(
        model_service=model_service,
        model_id=model_id,
        temperature=temperature,
        timeout_seconds=timeout_seconds,
        prompt=reduce_prompt,
        max_tokens=eval_reduce_max_tokens,
    )

    # Metrics
    estimated_input_tokens = compression_service._estimate_messages_tokens(messages)
    one_out_tokens = compression_service._estimate_text_tokens(one_pass.content)
    two_out_tokens = compression_service._estimate_text_tokens(reduce_result.content)
    facts = compression_service._extract_critical_facts(messages, max_facts=40)
    one_cov, one_missing = compression_service._critical_fact_coverage(one_pass.content, facts)
    two_cov, two_missing = compression_service._critical_fact_coverage(reduce_result.content, facts)

    two_stage_usage = _sum_usage([item["usage"] for item in map_results] + [reduce_result.usage])
    map_duration_ms = sum(int(item.get("duration_ms", 0)) for item in map_results)
    reduce_duration_ms = int(reduce_result.duration_ms)
    two_stage_duration_ms = map_duration_ms + reduce_duration_ms
    metrics = {
        "output_language": {
            "configured_mode": getattr(config, "compression_output_language", "auto"),
            "effective_language": output_language_code,
            "meta": output_language_meta,
        },
        "input_estimated_tokens": estimated_input_tokens,
        "one_pass": {
            "output_estimated_tokens": one_out_tokens,
            "compression_ratio": round(one_out_tokens / max(1, estimated_input_tokens), 3),
            "critical_fact_coverage": round(one_cov, 3),
            "missing_facts_sample": one_missing[:8],
            "usage": one_pass.usage,
            "duration_ms": int(one_pass.duration_ms),
        },
        "two_stage": {
            "chunk_count": len(chunks),
            "output_estimated_tokens": two_out_tokens,
            "compression_ratio": round(two_out_tokens / max(1, estimated_input_tokens), 3),
            "critical_fact_coverage": round(two_cov, 3),
            "missing_facts_sample": two_missing[:8],
            "usage_aggregate": two_stage_usage,
            "map_duration_ms": map_duration_ms,
            "reduce_duration_ms": reduce_duration_ms,
            "total_duration_ms": two_stage_duration_ms,
        },
        "delta": {
            "output_tokens_two_minus_one": two_out_tokens - one_out_tokens,
            "coverage_two_minus_one": round(two_cov - one_cov, 3),
            "duration_ms_two_minus_one": two_stage_duration_ms - int(one_pass.duration_ms),
        },
    }

    # Persist outputs
    (out_dir / "one_pass_summary.md").write_text(one_pass.content + "\n", encoding="utf-8")
    (out_dir / "two_stage_final_summary.md").write_text(reduce_result.content + "\n", encoding="utf-8")

    intermediate_lines = ["# Two-stage Intermediate Summaries", ""]
    for item in map_results:
        intermediate_lines.append(f"## Chunk {item['chunk_index']}")
        intermediate_lines.append(f"- Message count: {item['message_count']}")
        intermediate_lines.append(f"- Estimated input tokens: {item['estimated_input_tokens']}")
        intermediate_lines.append(f"- Usage: {json.dumps(item['usage'] or {}, ensure_ascii=True)}")
        intermediate_lines.append("")
        intermediate_lines.append(item["summary"])
        intermediate_lines.append("")
    (out_dir / "two_stage_intermediate.md").write_text("\n".join(intermediate_lines), encoding="utf-8")

    (out_dir / "raw_results.json").write_text(
        json.dumps(
            {
                "one_pass": {
                    "prompt": one_pass.prompt,
                    "summary": one_pass.content,
                    "usage": one_pass.usage,
                },
                "two_stage": {
                    "map_results": map_results,
                    "reduce_prompt": reduce_prompt,
                    "final_summary": reduce_result.content,
                    "reduce_usage": reduce_result.usage,
                    "reduce_duration_ms": int(reduce_result.duration_ms),
                },
                "facts_sample": facts[:20],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = _build_report_markdown(
        model_id=model_id,
        chunk_count=len(chunks),
        single_tokens_in=estimated_input_tokens,
        single_tokens_out=one_out_tokens,
        two_tokens_out=two_out_tokens,
        single_cov=one_cov,
        two_cov=two_cov,
        single_usage=one_pass.usage,
        two_usage=two_stage_usage,
        single_duration_ms=int(one_pass.duration_ms),
        two_duration_ms=two_stage_duration_ms,
        map_duration_ms=map_duration_ms,
        reduce_duration_ms=reduce_duration_ms,
    )
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    print(f"Saved comparison artifacts to: {out_dir}")
    print(f"One-pass coverage={one_cov:.3f}, two-stage coverage={two_cov:.3f}")
    print(f"One-pass out_tokens={one_out_tokens}, two-stage out_tokens={two_out_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
