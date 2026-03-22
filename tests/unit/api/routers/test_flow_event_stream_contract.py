"""Contract tests for flow_event-only SSE streams."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest
from fastapi import HTTPException

from src.api.routers import chat as chat_router
from src.api.routers import translation as translation_router
from src.api.routers import workflows as workflows_router
from src.application.flow.flow_stream_runtime import FlowStreamRuntime


async def _collect_sse_payloads(streaming_response: Any) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    async for chunk in streaming_response.body_iterator:
        text = chunk.decode("utf-8") if isinstance(chunk, (bytes, bytearray)) else str(chunk)
        for line in text.splitlines():
            if not line.startswith("data: "):
                continue
            payloads.append(json.loads(line[6:]))
    return payloads


def _assert_flow_event_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    assert set(payload.keys()) == {"flow_event"}
    flow_event = payload["flow_event"]
    assert isinstance(flow_event, dict)
    assert isinstance(flow_event.get("event_id"), str) and flow_event["event_id"]
    assert isinstance(flow_event.get("seq"), int) and flow_event["seq"] >= 1
    assert isinstance(flow_event.get("ts"), int) and flow_event["ts"] >= 0
    assert isinstance(flow_event.get("stream_id"), str) and flow_event["stream_id"]
    assert isinstance(flow_event.get("event_type"), str) and flow_event["event_type"]
    assert flow_event.get("stage") in {"transport", "content", "tool", "orchestration", "meta"}
    assert isinstance(flow_event.get("payload"), dict)
    return flow_event


def _assert_seq_strictly_increasing(events: List[Dict[str, Any]]) -> None:
    seqs = [event["seq"] for event in events]
    assert seqs == sorted(seqs)
    assert len(seqs) == len(set(seqs))


class _FakeStorage:
    async def get_session(self, *_args, **_kwargs):
        return {}

    async def truncate_messages_after(self, *_args, **_kwargs):
        return None


class _FakeChatAgent:
    def __init__(self):
        self.storage = _FakeStorage()

    async def process_chat_stream(self, *_args, **_kwargs):
        async for event in self.process_message_stream(*_args, **_kwargs):
            yield event

    async def process_message_stream(self, *_args, **_kwargs):
        yield "hello"
        yield " world"
        yield {"type": "usage", "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}}

    async def process_compare_stream(self, *_args, **_kwargs):
        yield {"type": "model_start", "model_id": "m1", "model_name": "Model-1"}
        yield {"type": "model_chunk", "model_id": "m1", "chunk": "A"}
        yield {
            "type": "model_done",
            "model_id": "m1",
            "model_name": "Model-1",
            "content": "Answer A",
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }
        yield {"type": "compare_complete", "model_results": {"m1": {"content": "Answer A"}}}

    async def truncate_messages_after(self, **kwargs):
        await self.storage.truncate_messages_after(**kwargs)

    async def compress_context_stream(self, **kwargs):
        from src.infrastructure.compression.compression_service import CompressionService

        compression_service = CompressionService(self.storage)
        async for chunk in compression_service.compress_context_stream(**kwargs):
            yield chunk


class _FakeChatAgentWithCompareError(_FakeChatAgent):
    async def process_compare_stream(self, *_args, **_kwargs):
        yield {"type": "model_start", "model_id": "m1", "model_name": "Model-1"}
        yield {"type": "error", "error": "compare failed"}
        yield {"type": "model_chunk", "model_id": "m1", "chunk": "should_not_emit"}


@pytest.mark.asyncio
async def test_chat_stream_contract_flow_event_only():
    runtime = FlowStreamRuntime()
    agent = _FakeChatAgent()
    request = chat_router.ChatRequest(session_id="session-1", message="hi")

    response = await chat_router.chat_stream(request=request, agent=agent, runtime=runtime)
    payloads = await _collect_sse_payloads(response)
    events = [_assert_flow_event_envelope(payload) for payload in payloads]
    _assert_seq_strictly_increasing(events)

    event_types = [event["event_type"] for event in events]
    assert event_types[0] == "stream_started"
    assert event_types[-1] == "stream_ended"
    assert "usage_reported" in event_types
    assert event_types.count("text_delta") == 2

    for event in events:
        if event["event_type"] == "text_delta":
            assert isinstance(event["payload"].get("text"), str)
            assert event["payload"]["text"]


@pytest.mark.asyncio
async def test_chat_compare_contract_flow_event_only():
    agent = _FakeChatAgent()
    request = chat_router.CompareRequest(
        session_id="session-2",
        message="compare this",
        model_ids=["p:m1", "p:m2"],
    )

    response = await chat_router.chat_compare(request=request, agent=agent)
    payloads = await _collect_sse_payloads(response)
    events = [_assert_flow_event_envelope(payload) for payload in payloads]
    _assert_seq_strictly_increasing(events)

    event_types = [event["event_type"] for event in events]
    assert event_types[0] == "stream_started"
    assert event_types[-1] == "stream_ended"
    assert "compare_model_started" in event_types
    assert "compare_model_finished" in event_types
    assert "compare_completed" in event_types

    text_deltas = [event for event in events if event["event_type"] == "text_delta"]
    assert len(text_deltas) == 1
    assert text_deltas[0]["payload"]["text"] == "A"
    assert text_deltas[0]["payload"]["model_id"] == "m1"


@pytest.mark.asyncio
async def test_chat_compare_stream_error_terminates_early():
    agent = _FakeChatAgentWithCompareError()
    request = chat_router.CompareRequest(
        session_id="session-2b",
        message="compare this",
        model_ids=["p:m1", "p:m2"],
    )

    response = await chat_router.chat_compare(request=request, agent=agent)
    payloads = await _collect_sse_payloads(response)
    events = [_assert_flow_event_envelope(payload) for payload in payloads]
    _assert_seq_strictly_increasing(events)

    event_types = [event["event_type"] for event in events]
    assert event_types == ["stream_started", "compare_model_started", "stream_error"]
    assert events[-1]["payload"]["error"] == "compare failed"


@pytest.mark.asyncio
async def test_chat_compress_contract_flow_event_only(monkeypatch):
    class _FakeCompressionService:
        def __init__(self, _storage):
            pass

        async def compress_context_stream(self, **_kwargs):
            yield "summary"
            yield {"type": "compression_complete", "message_id": "mid-1", "compressed_count": 3}

    monkeypatch.setattr(
        "src.infrastructure.compression.compression_service.CompressionService",
        _FakeCompressionService,
    )

    agent = _FakeChatAgent()
    request = chat_router.CompressContextRequest(session_id="session-3")
    response = await chat_router.compress_context(request=request, agent=agent)

    payloads = await _collect_sse_payloads(response)
    events = [_assert_flow_event_envelope(payload) for payload in payloads]
    _assert_seq_strictly_increasing(events)

    event_types = [event["event_type"] for event in events]
    assert event_types == ["stream_started", "text_delta", "compression_completed", "stream_ended"]
    assert events[1]["payload"]["text"] == "summary"
    assert events[2]["payload"]["message_id"] == "mid-1"
    assert events[2]["payload"]["compressed_count"] == 3


@pytest.mark.asyncio
async def test_chat_compress_unknown_event_maps_to_stream_error_and_stops(monkeypatch):
    class _FakeCompressionService:
        def __init__(self, _storage):
            pass

        async def compress_context_stream(self, **_kwargs):
            yield {"type": "unknown_event", "foo": "bar"}
            yield "summary"
            yield {"type": "compression_complete", "message_id": "mid-2", "compressed_count": 1}

    monkeypatch.setattr(
        "src.infrastructure.compression.compression_service.CompressionService",
        _FakeCompressionService,
    )

    agent = _FakeChatAgent()
    request = chat_router.CompressContextRequest(session_id="session-legacy")
    response = await chat_router.compress_context(request=request, agent=agent)

    payloads = await _collect_sse_payloads(response)
    events = [_assert_flow_event_envelope(payload) for payload in payloads]
    _assert_seq_strictly_increasing(events)

    event_types = [event["event_type"] for event in events]
    assert event_types == ["stream_started", "stream_error"]
    assert events[1]["payload"]["error"] == "unsupported compression stream event type: unknown_event"


@pytest.mark.asyncio
async def test_translate_contract_flow_event_only(monkeypatch):
    class _FakeTranslationService:
        async def translate_stream(self, **_kwargs):
            yield {"type": "language_detected", "language": "en", "confidence": 0.99, "detector": "test"}
            yield "ni hao"
            yield {
                "type": "translation_complete",
                "detected_source_language": "en",
                "detected_source_confidence": 0.99,
                "effective_target_language": "zh",
            }

    monkeypatch.setattr("src.application.translation.translation_service.TranslationService", _FakeTranslationService)

    request = translation_router.TranslateRequest(text="hello", target_language="zh")
    response = await translation_router.translate_text(request)

    payloads = await _collect_sse_payloads(response)
    events = [_assert_flow_event_envelope(payload) for payload in payloads]
    _assert_seq_strictly_increasing(events)

    event_types = [event["event_type"] for event in events]
    assert event_types == [
        "stream_started",
        "language_detected",
        "text_delta",
        "translation_completed",
        "stream_ended",
    ]
    assert events[0]["payload"]["context_type"] == "translation"
    assert events[2]["payload"]["text"] == "ni hao"


class _FakeWorkflow:
    enabled = True


class _FakeWorkflowConfigService:
    async def get_workflow(self, _workflow_id: str):
        return _FakeWorkflow()


class _FakeWorkflowExecutionService:
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def execute_stream(self, workflow, inputs, **kwargs):
        self.calls.append({"workflow": workflow, "inputs": inputs, **kwargs})
        yield {"type": "text_delta", "text": "rewritten"}
        yield {"type": "text_delta", "text": " text"}


@pytest.mark.asyncio
async def test_workflow_editor_rewrite_contract_flow_event_only():
    execution_service = _FakeWorkflowExecutionService()
    request = workflows_router.WorkflowRunRequest(
        session_id="session-editor-1",
        context_type="project",
        project_id="proj-1",
        stream_mode="editor_rewrite",
        inputs={
            "_selected_text": "source text",
            "_context_before": "before",
            "_context_after": "after",
        },
    )

    response = await workflows_router.run_workflow_stream(
        workflow_id="wf_inline_rewrite_default",
        request=request,
        service=_FakeWorkflowConfigService(),
        execution_service=execution_service,
    )
    payloads = await _collect_sse_payloads(response)
    events = [_assert_flow_event_envelope(payload) for payload in payloads]
    _assert_seq_strictly_increasing(events)

    event_types = [event["event_type"] for event in events]
    assert event_types == ["stream_started", "text_delta", "text_delta", "stream_ended"]
    assert events[0]["payload"]["context_type"] == "project"
    assert events[1]["payload"]["text"] == "rewritten"
    assert events[2]["payload"]["text"] == " text"
    assert len(execution_service.calls) == 1
    assert execution_service.calls[0]["stream_mode"] == "editor_rewrite"
    assert execution_service.calls[0]["context_type"] == "project"
    assert execution_service.calls[0]["project_id"] == "proj-1"


@pytest.mark.asyncio
async def test_workflow_stream_requires_project_id_for_project_context():
    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.run_workflow_stream(
            workflow_id="wf_inline_rewrite_default",
            request=workflows_router.WorkflowRunRequest(
                session_id="session-editor-2",
                context_type="project",
                stream_mode="editor_rewrite",
                inputs={"_selected_text": "source text"},
            ),
            service=_FakeWorkflowConfigService(),
            execution_service=_FakeWorkflowExecutionService(),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_workflow_stream_write_mode_requires_project_context():
    with pytest.raises(HTTPException) as exc_info:
        await workflows_router.run_workflow_stream(
            workflow_id="wf_inline_rewrite_default",
            request=workflows_router.WorkflowRunRequest(
                session_id="session-editor-3",
                context_type="workflow",
                write_mode="overwrite",
                inputs={"_selected_text": "source text"},
            ),
            service=_FakeWorkflowConfigService(),
            execution_service=_FakeWorkflowExecutionService(),
        )

    assert exc_info.value.status_code == 400
