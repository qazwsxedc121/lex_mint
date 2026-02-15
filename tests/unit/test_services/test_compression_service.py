import asyncio
from types import SimpleNamespace

from src.api.services.compression_service import CompressionService


def _build_messages(count: int, content_size: int) -> list[dict]:
    messages = []
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        messages.append(
            {
                "id": f"m{i}",
                "role": role,
                "content": f"{role}-{i}-" + ("x" * content_size),
            }
        )
    return messages


def test_chunk_messages_keeps_progress_with_overlap():
    svc = CompressionService(storage=SimpleNamespace())
    messages = _build_messages(8, 120)

    chunks = svc._chunk_messages(messages, target_tokens=80, overlap_messages=1)

    assert len(chunks) >= 2
    assert chunks[0]
    assert chunks[1]
    # Overlap should repeat the boundary message.
    assert chunks[0][-1]["id"] == chunks[1][0]["id"]


def test_compress_with_local_gguf_uses_single_pass_for_small_input(monkeypatch):
    svc = CompressionService(storage=SimpleNamespace())
    messages = _build_messages(2, 40)
    config = SimpleNamespace(
        local_gguf_n_ctx=2048,
        local_gguf_max_tokens=256,
        temperature=0.3,
        prompt_template="Summarize:\n{formatted_messages}",
    )
    calls = {"map": 0, "reduce": 0}

    def fake_map(**kwargs):
        calls["map"] += 1
        return "single-pass-summary"

    def fake_reduce(**kwargs):
        calls["reduce"] += 1
        return "reduce-summary"

    monkeypatch.setattr(svc, "_summarize_message_chunk_with_local", fake_map)
    monkeypatch.setattr(svc, "_summarize_text_group_with_local", fake_reduce)

    summary, meta = svc._compress_with_local_gguf(
        local_llm=SimpleNamespace(),
        config=config,
        compressible=messages,
    )

    assert summary == "single-pass-summary"
    assert meta["mode"] == "single_pass"
    assert calls["map"] == 1
    assert calls["reduce"] == 0


def test_compress_with_local_gguf_uses_hierarchy_for_long_input(monkeypatch):
    svc = CompressionService(storage=SimpleNamespace())
    messages = _build_messages(8, 360)
    config = SimpleNamespace(
        local_gguf_n_ctx=512,
        local_gguf_max_tokens=192,
        temperature=0.3,
        prompt_template="Summarize:\n{formatted_messages}",
    )
    calls = {"map": 0, "reduce": 0}

    def fake_map(**kwargs):
        calls["map"] += 1
        return f"chunk-summary-{calls['map']}"

    def fake_reduce(**kwargs):
        calls["reduce"] += 1
        return f"merged-summary-{calls['reduce']}"

    monkeypatch.setattr(svc, "_summarize_message_chunk_with_local", fake_map)
    monkeypatch.setattr(svc, "_summarize_text_group_with_local", fake_reduce)

    summary, meta = svc._compress_with_local_gguf(
        local_llm=SimpleNamespace(),
        config=config,
        compressible=messages,
    )

    assert meta["mode"] == "hierarchical"
    assert meta["initial_chunks"] > 1
    assert meta["levels"] >= 2
    assert calls["map"] >= 2
    assert calls["reduce"] >= 1
    assert summary.startswith("merged-summary-")


def test_local_quality_guard_repairs_missing_facts():
    svc = CompressionService(storage=SimpleNamespace())
    messages = [
        {
            "role": "user",
            "content": "Use ./venv/bin/python for tests and check https://example.com/docs.",
        }
    ]
    config = SimpleNamespace(
        temperature=0.3,
        quality_guard_enabled=True,
        quality_guard_min_coverage=0.9,
        quality_guard_max_facts=10,
    )

    class FakeLocalLLM:
        def complete_prompt(self, *_args, **_kwargs):
            return "Summary includes ./venv/bin/python and https://example.com/docs."

    summary, meta = svc._run_local_quality_guard(
        local_llm=FakeLocalLLM(),
        config=config,
        source_messages=messages,
        summary="Short summary only.",
        max_tokens=128,
        output_language_code=None,
    )

    assert meta["enabled"] is True
    assert meta["repaired"] is True
    assert meta["passed"] is True
    assert "https://example.com/docs" in summary


def test_local_quality_guard_fallback_appends_missing_facts():
    svc = CompressionService(storage=SimpleNamespace())
    messages = [
        {
            "role": "user",
            "content": "Command: ./venv/bin/python and file src/api/main.py.",
        }
    ]
    config = SimpleNamespace(
        temperature=0.3,
        quality_guard_enabled=True,
        quality_guard_min_coverage=0.95,
        quality_guard_max_facts=10,
    )

    class EmptyLocalLLM:
        def complete_prompt(self, *_args, **_kwargs):
            return ""

    summary, meta = svc._run_local_quality_guard(
        local_llm=EmptyLocalLLM(),
        config=config,
        source_messages=messages,
        summary="Still missing details.",
        max_tokens=128,
        output_language_code=None,
    )

    assert meta["fallback_injected"] is True
    assert "### Critical Facts" in summary
    assert "./venv/bin/python" in summary or "src/api/main.py" in summary


def test_build_compression_metrics_contains_ratio_fields():
    svc = CompressionService(storage=SimpleNamespace())
    metrics = svc._build_compression_metrics(
        started_at=0.0,
        input_tokens=1000,
        output_text="x" * 800,
        mode="hierarchical",
        levels=2,
        initial_chunks=4,
    )

    assert metrics["mode"] == "hierarchical"
    assert metrics["levels"] == 2
    assert metrics["initial_chunks"] == 4
    assert 0.0 <= metrics["estimated_compression_ratio"] <= 1.0
    assert 0.0 <= metrics["estimated_reduction_ratio"] <= 1.0


def test_reduce_prompt_reuses_normal_compression_template():
    svc = CompressionService(storage=SimpleNamespace())
    config = SimpleNamespace(
        prompt_template="Header\n## Output Format\n- A\n\n{formatted_messages}\nFooter",
    )

    prompt = svc._build_reduce_prompt(config, ["Part 1", "Part 2"], output_language_code=None)

    assert "## Output Format" in prompt
    assert "<partial_summaries>" in prompt
    assert "[Summary 1]" in prompt
    assert "Output only the merged summary." in prompt


def test_resolve_output_language_modes():
    svc = CompressionService(storage=SimpleNamespace())
    messages = [{"role": "user", "content": "This is an english test message."}]

    auto_config = SimpleNamespace(compression_output_language="auto")
    auto_code, auto_meta = svc._resolve_output_language_for_messages(messages, auto_config)
    assert auto_meta["mode"] == "auto"
    assert auto_code in (None, "en")

    none_config = SimpleNamespace(compression_output_language="none")
    none_code, none_meta = svc._resolve_output_language_for_messages(messages, none_config)
    assert none_code is None
    assert none_meta["mode"] == "none"

    fixed_config = SimpleNamespace(compression_output_language="zh")
    fixed_code, fixed_meta = svc._resolve_output_language_for_messages(messages, fixed_config)
    assert fixed_code == "zh"
    assert fixed_meta["mode"] == "zh"


def test_compress_with_model_config_uses_single_pass_when_within_budget():
    svc = CompressionService(storage=SimpleNamespace())
    messages = _build_messages(2, 50)
    config = SimpleNamespace(
        hierarchical_chunk_target_tokens=0,
        hierarchical_chunk_overlap_messages=1,
        hierarchical_reduce_target_tokens=0,
        hierarchical_reduce_overlap_items=1,
        hierarchical_max_levels=4,
        compression_metrics_enabled=True,
        prompt_template="Summarize:\n{formatted_messages}",
    )

    class FakeAdapter:
        async def invoke(self, _llm, _messages):
            return SimpleNamespace(content="single summary")

    def llm_factory(*, max_tokens: int):
        return SimpleNamespace(max_tokens=max_tokens)

    summary, meta = asyncio.run(
        svc._compress_with_model_config(
            adapter=FakeAdapter(),
            llm_factory=llm_factory,
            config=config,
            compressible=messages,
            context_length_tokens=4096,
            output_language_code=None,
            output_language_meta={"mode": "none"},
        )
    )

    assert summary == "single summary"
    assert meta["mode"] == "single_pass"
    assert meta["initial_chunks"] == 1


def test_compress_with_model_config_uses_hierarchy_when_over_budget():
    svc = CompressionService(storage=SimpleNamespace())
    messages = _build_messages(8, 420)
    config = SimpleNamespace(
        hierarchical_chunk_target_tokens=0,
        hierarchical_chunk_overlap_messages=1,
        hierarchical_reduce_target_tokens=0,
        hierarchical_reduce_overlap_items=1,
        hierarchical_max_levels=4,
        compression_metrics_enabled=True,
        prompt_template="Summarize:\n{formatted_messages}",
    )
    calls = {"map": 0, "reduce": 0}

    class FakeAdapter:
        async def invoke(self, _llm, messages_payload):
            prompt = messages_payload[0].content
            if "<partial_summaries>" in prompt:
                calls["reduce"] += 1
                return SimpleNamespace(content=f"reduce-{calls['reduce']}")
            calls["map"] += 1
            return SimpleNamespace(content=f"map-{calls['map']}")

    def llm_factory(*, max_tokens: int):
        return SimpleNamespace(max_tokens=max_tokens)

    summary, meta = asyncio.run(
        svc._compress_with_model_config(
            adapter=FakeAdapter(),
            llm_factory=llm_factory,
            config=config,
            compressible=messages,
            context_length_tokens=512,
            output_language_code=None,
            output_language_meta={"mode": "none"},
        )
    )

    assert meta["mode"] == "hierarchical"
    assert meta["initial_chunks"] > 1
    assert calls["map"] >= 2
    assert calls["reduce"] >= 1
    assert summary.startswith("reduce-")


def test_resolve_effective_compression_model_id():
    svc = CompressionService(storage=SimpleNamespace())

    same_model = svc._resolve_effective_compression_model_id(
        session_model_id="openai:gpt-4o-mini",
        compression_model_id="same_as_chat",
        provider="model_config",
    )
    assert same_model == "openai:gpt-4o-mini"

    explicit_model = svc._resolve_effective_compression_model_id(
        session_model_id="openai:gpt-4o-mini",
        compression_model_id="deepseek:deepseek-chat",
        provider="model_config",
    )
    assert explicit_model == "deepseek:deepseek-chat"

    local_provider = svc._resolve_effective_compression_model_id(
        session_model_id="openai:gpt-4o-mini",
        compression_model_id="deepseek:deepseek-chat",
        provider="local_gguf",
    )
    assert local_provider == "openai:gpt-4o-mini"
