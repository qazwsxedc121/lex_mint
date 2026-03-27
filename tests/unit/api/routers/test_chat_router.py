"""Unit tests for chat router endpoint wrappers and stream helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional

import pytest
from fastapi import HTTPException

from src.api.routers import chat as chat_router
from src.application.flow.flow_event_emitter import FlowEventEmitter
from src.application.flow.flow_stream_runtime import (
    FlowReplayCursorGoneError,
    FlowStreamContextMismatchError,
    FlowStreamNotFoundError,
    FlowStreamRuntime,
)


async def _collect_sse_payloads(streaming_response: Any) -> List[Dict[str, Any]]:
    payloads: List[Dict[str, Any]] = []
    async for chunk in streaming_response.body_iterator:
        text = chunk.decode("utf-8") if isinstance(chunk, (bytes, bytearray)) else str(chunk)
        for line in text.splitlines():
            if line.startswith("data: "):
                payloads.append(json.loads(line[6:]))
    return payloads


async def _async_iter(items: Iterable[Any]) -> AsyncIterator[Any]:
    for item in items:
        yield item


class _FakeAgent:
    def __init__(self) -> None:
        self.process_message_result = ("answer", [{"type": "search", "title": "Result"}])
        self.process_message_error: Exception | None = None
        self.stream_items: list[Any] = []
        self.stream_error: Exception | None = None
        self.compare_items: list[Any] = []
        self.compare_error: Exception | None = None
        self.compress_items: list[Any] = []
        self.compress_error: Exception | None = None
        self.calls: list[tuple[str, Any]] = []

    async def process_message(self, session_id: str, message: str, **kwargs):
        self.calls.append(("process_message", {"session_id": session_id, "message": message, **kwargs}))
        if self.process_message_error is not None:
            raise self.process_message_error
        return self.process_message_result

    async def truncate_messages_after(self, **kwargs):
        self.calls.append(("truncate", kwargs))

    def process_chat_stream(self, session_id: str, message: str, **kwargs):
        self.calls.append(("process_chat_stream", {"session_id": session_id, "message": message, **kwargs}))
        if self.stream_error is not None:
            async def _raiser():
                raise self.stream_error
                yield  # pragma: no cover
            return _raiser()
        return _async_iter(self.stream_items)

    async def delete_message(self, **kwargs):
        self.calls.append(("delete_message", kwargs))
        error = kwargs.pop("_error", None)
        if error is not None:
            raise error

    async def update_message_content(self, **kwargs):
        self.calls.append(("update_message_content", kwargs))
        error = kwargs.pop("_error", None)
        if error is not None:
            raise error

    async def append_separator(self, **kwargs):
        self.calls.append(("append_separator", kwargs))
        return "sep-1"

    async def clear_all_messages(self, **kwargs):
        self.calls.append(("clear_all_messages", kwargs))

    def compress_context_stream(self, **kwargs):
        self.calls.append(("compress_context_stream", kwargs))
        if self.compress_error is not None:
            async def _raiser():
                raise self.compress_error
                yield  # pragma: no cover
            return _raiser()
        return _async_iter(self.compress_items)

    def process_compare_stream(self, session_id: str, message: str, model_ids: list[str], **kwargs):
        self.calls.append(
            ("process_compare_stream", {"session_id": session_id, "message": message, "model_ids": model_ids, **kwargs})
        )
        if self.compare_error is not None:
            async def _raiser():
                raise self.compare_error
                yield  # pragma: no cover
            return _raiser()
        return _async_iter(self.compare_items)


class _UploadFile:
    def __init__(self, filename: str):
        self.filename = filename


class _FakeFileService:
    def __init__(self, attachments_dir: Path):
        self.attachments_dir = attachments_dir
        self.saved_result = {"filename": "note.txt", "temp_path": "/tmp/note.txt"}
        self.validate_error: Exception | None = None
        self.save_error: Exception | None = None
        self.file_path: Path | None = None

    async def validate_file(self, _file: Any) -> None:
        if self.validate_error is not None:
            raise self.validate_error

    async def save_temp_file(self, _session_id: str, _file: Any) -> dict[str, Any]:
        if self.save_error is not None:
            raise self.save_error
        return dict(self.saved_result)

    def get_file_path(self, _session_id: str, _message_index: int, _filename: str) -> Path | None:
        return self.file_path


@pytest.mark.asyncio
async def test_chat_route_maps_success_and_errors():
    agent = _FakeAgent()
    agent.process_message_result = (
        "hello",
        [
            {"type": "search", "title": "Search", "url": "https://example.com"},
            {"type": "invalid"},
        ],
    )

    response = await chat_router.chat(
        chat_router.ChatRequest(session_id="session-1", message="hi"),
        agent=agent,  # type: ignore[arg-type]
    )
    assert response.response == "hello"
    assert response.sources and len(response.sources) == 1

    with pytest.raises(HTTPException) as exc_info:
        await chat_router.chat(
            chat_router.ChatRequest(session_id="session-1", message="hi", context_type="project"),
            agent=agent,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    agent.process_message_error = FileNotFoundError()
    with pytest.raises(HTTPException) as exc_info:
        await chat_router.chat(
            chat_router.ChatRequest(session_id="session-1", message="hi"),
            agent=agent,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    agent.process_message_error = ValueError("bad input")
    with pytest.raises(HTTPException) as exc_info:
        await chat_router.chat(
            chat_router.ChatRequest(session_id="session-1", message="hi"),
            agent=agent,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    agent.process_message_error = RuntimeError("boom")
    with pytest.raises(HTTPException) as exc_info:
        await chat_router.chat(
            chat_router.ChatRequest(session_id="session-1", message="hi"),
            agent=agent,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_stream_helpers_build_and_produce_payloads():
    agent = _FakeAgent()
    agent.stream_items = ["part-1", {"done": True}]
    request = chat_router.ChatRequest(
        session_id="session-1",
        message="stream me",
        truncate_after_index=2,
        skip_user_message=True,
        reasoning_effort="medium",
        use_web_search=True,
    )

    stream_fn = await chat_router._build_stream_fn(request, agent)  # type: ignore[arg-type]
    assert [item async for item in stream_fn] == ["part-1", {"done": True}]
    truncate_calls = [payload for name, payload in agent.calls if name == "truncate"]
    assert truncate_calls == [
        {
            "session_id": "session-1",
            "keep_until_index": 2,
            "context_type": "chat",
            "project_id": None,
        }
    ]

    runtime = FlowStreamRuntime()
    runtime.create_stream(stream_id="stream-1", conversation_id="session-1", context_type="chat", project_id=None)
    await chat_router._run_chat_stream_producer(
        request=chat_router.ChatRequest(session_id="session-1", message="stream me"),
        agent=agent,  # type: ignore[arg-type]
        runtime=runtime,
        stream_id="stream-1",
    )
    stored = list(runtime.get_stream("stream-1").events)
    assert stored[0]["flow_event"]["event_type"] == "stream_started"
    assert chat_router._is_terminal_payload(stored[-1]) is True

    for error in (FileNotFoundError(), ValueError("bad stream"), RuntimeError("crash")):
        runtime = FlowStreamRuntime()
        runtime.create_stream(stream_id="stream-err", conversation_id="session-1", context_type="chat", project_id=None)
        agent = _FakeAgent()
        agent.stream_error = error
        await chat_router._run_chat_stream_producer(
            request=chat_router.ChatRequest(session_id="session-1", message="stream me"),
            agent=agent,  # type: ignore[arg-type]
            runtime=runtime,
            stream_id="stream-err",
        )
        last_payload = list(runtime.get_stream("stream-err").events)[-1]
        assert last_payload["flow_event"]["event_type"] == "stream_error"


@pytest.mark.asyncio
async def test_chat_stream_and_resume_routes(monkeypatch):
    runtime = FlowStreamRuntime()

    async def _fake_producer(*, request, runtime, stream_id, **_kwargs):
        emitter = FlowEventEmitter(stream_id=stream_id, conversation_id=request.session_id)
        runtime.append_payload(stream_id, emitter.emit_started(context_type=request.context_type))
        runtime.append_payload(stream_id, emitter.emit_ended())

    monkeypatch.setattr(chat_router, "_run_chat_stream_producer", _fake_producer)

    response = await chat_router.chat_stream(
        chat_router.ChatRequest(session_id="session-1", message="hi"),
        agent=_FakeAgent(),  # type: ignore[arg-type]
        runtime=runtime,
    )
    payloads = await _collect_sse_payloads(response)
    assert [payload["flow_event"]["event_type"] for payload in payloads] == ["stream_started", "stream_ended"]

    with pytest.raises(HTTPException) as exc_info:
        await chat_router.chat_stream(
            chat_router.ChatRequest(session_id="session-1", message="hi", context_type="project"),
            agent=_FakeAgent(),  # type: ignore[arg-type]
            runtime=runtime,
        )
    assert exc_info.value.status_code == 400

    class _OverloadedRuntime(FlowStreamRuntime):
        def create_stream(self, **kwargs):
            raise RuntimeError("overloaded")

    with pytest.raises(HTTPException) as exc_info:
        await chat_router.chat_stream(
            chat_router.ChatRequest(session_id="session-1", message="hi"),
            agent=_FakeAgent(),  # type: ignore[arg-type]
            runtime=_OverloadedRuntime(),
        )
    assert exc_info.value.status_code == 503

    resume_runtime = FlowStreamRuntime()
    resume_runtime.create_stream(stream_id="stream-resume", conversation_id="session-1", context_type="chat", project_id=None)
    emitter = FlowEventEmitter(stream_id="stream-resume", conversation_id="session-1")
    started = emitter.emit_started(context_type="chat")
    done = emitter.emit_ended()
    resume_runtime.append_payload("stream-resume", started)
    resume_runtime.append_payload("stream-resume", done)

    response = await chat_router.resume_chat_stream(
        chat_router.ResumeStreamRequest(
            session_id="session-1",
            stream_id="stream-resume",
            last_event_id=started["flow_event"]["event_id"],
        ),
        runtime=resume_runtime,
    )
    payloads = await _collect_sse_payloads(response)
    assert payloads[0]["flow_event"]["event_type"] == "resume_started"
    assert payloads[1]["flow_event"]["event_type"] == "stream_ended"


@pytest.mark.asyncio
async def test_resume_chat_stream_maps_runtime_errors():
    class _ResumeRuntime:
        def resume_subscribe(self, **_kwargs):
            raise FlowStreamNotFoundError("missing")

    with pytest.raises(HTTPException) as exc_info:
        await chat_router.resume_chat_stream(
            chat_router.ResumeStreamRequest(session_id="s1", stream_id="stream", last_event_id="evt-1"),
            runtime=_ResumeRuntime(),  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    class _CursorGoneRuntime:
        def resume_subscribe(self, **_kwargs):
            raise FlowReplayCursorGoneError("gone")

    with pytest.raises(HTTPException) as exc_info:
        await chat_router.resume_chat_stream(
            chat_router.ResumeStreamRequest(session_id="s1", stream_id="stream", last_event_id="evt-1"),
            runtime=_CursorGoneRuntime(),  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 410

    class _MismatchRuntime:
        def resume_subscribe(self, **_kwargs):
            raise FlowStreamContextMismatchError("mismatch")

    with pytest.raises(HTTPException) as exc_info:
        await chat_router.resume_chat_stream(
            chat_router.ResumeStreamRequest(session_id="s1", stream_id="stream", last_event_id="evt-1"),
            runtime=_MismatchRuntime(),  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 409

    with pytest.raises(HTTPException) as exc_info:
        await chat_router.resume_chat_stream(
            chat_router.ResumeStreamRequest(
                session_id="s1",
                stream_id="stream",
                last_event_id="evt-1",
                context_type="project",
            ),
            runtime=FlowStreamRuntime(),
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_and_download_routes(tmp_path):
    attachments_dir = tmp_path / "attachments"
    attachments_dir.mkdir()
    file_service = _FakeFileService(attachments_dir)

    metadata = await chat_router.upload_file(
        session_id="session-1",
        file=_UploadFile("note.txt"),  # type: ignore[arg-type]
        file_service=file_service,  # type: ignore[arg-type]
    )
    assert metadata["filename"] == "note.txt"

    file_service.validate_error = ValueError("too large")
    with pytest.raises(HTTPException) as exc_info:
        await chat_router.upload_file(
            session_id="session-1",
            file=_UploadFile("note.txt"),  # type: ignore[arg-type]
            file_service=file_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    file_service.validate_error = None
    file_service.save_error = RuntimeError("disk failed")
    with pytest.raises(HTTPException) as exc_info:
        await chat_router.upload_file(
            session_id="session-1",
            file=_UploadFile("note.txt"),  # type: ignore[arg-type]
            file_service=file_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 500

    download_path = attachments_dir / "note.txt"
    download_path.write_text("hello", encoding="utf-8")
    file_service.file_path = download_path

    response = await chat_router.download_attachment(
        "session-1",
        0,
        "note.txt",
        file_service=file_service,  # type: ignore[arg-type]
    )
    assert Path(response.path) == download_path

    with pytest.raises(HTTPException) as exc_info:
        await chat_router.download_attachment(
            "session-1",
            0,
            "note.txt",
            context_type="project",
            project_id=None,
            file_service=file_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    file_service.file_path = None
    with pytest.raises(HTTPException) as exc_info:
        await chat_router.download_attachment(
            "session-1",
            0,
            "note.txt",
            file_service=file_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    outside_path = tmp_path / "outside.txt"
    outside_path.write_text("nope", encoding="utf-8")
    file_service.file_path = outside_path
    with pytest.raises(HTTPException) as exc_info:
        await chat_router.download_attachment(
            "session-1",
            0,
            "note.txt",
            file_service=file_service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_message_mutation_routes_and_compare_stream():
    class _MutationAgent(_FakeAgent):
        async def delete_message(self, **kwargs):
            self.calls.append(("delete_message", kwargs))
            marker = kwargs.get("message_id", kwargs.get("message_index"))
            if marker == "missing":
                raise FileNotFoundError()
            if marker == -1:
                raise IndexError("bad index")
            if marker == "bad-value":
                raise ValueError("bad value")
            if marker == "boom":
                raise RuntimeError("boom")

        async def update_message_content(self, **kwargs):
            self.calls.append(("update_message_content", kwargs))
            if kwargs["message_id"] == "missing":
                raise FileNotFoundError()
            if kwargs["message_id"] == "bad":
                raise ValueError("bad")
            if kwargs["message_id"] == "boom":
                raise RuntimeError("boom")

        async def append_separator(self, **kwargs):
            self.calls.append(("append_separator", kwargs))
            if kwargs["session_id"] == "missing":
                raise FileNotFoundError()
            if kwargs["session_id"] == "bad":
                raise ValueError("bad")
            if kwargs["session_id"] == "boom":
                raise RuntimeError("boom")
            return "sep-1"

        async def clear_all_messages(self, **kwargs):
            self.calls.append(("clear_all_messages", kwargs))
            if kwargs["session_id"] == "missing":
                raise FileNotFoundError()
            if kwargs["session_id"] == "bad":
                raise ValueError("bad")
            if kwargs["session_id"] == "boom":
                raise RuntimeError("boom")

    agent = _MutationAgent()

    result = await chat_router.delete_message(
        chat_router.DeleteMessageRequest(session_id="s1", message_id="m1"),
        agent=agent,  # type: ignore[arg-type]
    )
    assert result["success"] is True

    result = await chat_router.delete_message(
        chat_router.DeleteMessageRequest(session_id="s1", message_index=1),
        agent=agent,  # type: ignore[arg-type]
    )
    assert result["success"] is True

    with pytest.raises(HTTPException) as exc_info:
        await chat_router.delete_message(
            chat_router.DeleteMessageRequest(session_id="s1"),
            agent=agent,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    for request, expected_status in [
        (chat_router.DeleteMessageRequest(session_id="s1", message_id="missing"), 404),
        (chat_router.DeleteMessageRequest(session_id="s1", message_index=-1), 400),
        (chat_router.DeleteMessageRequest(session_id="s1", message_id="bad-value"), 400),
        (chat_router.DeleteMessageRequest(session_id="s1", message_id="boom"), 500),
        (chat_router.DeleteMessageRequest(session_id="s1", message_id="m1", context_type="project"), 400),
    ]:
        with pytest.raises(HTTPException) as exc_info:
            await chat_router.delete_message(request, agent=agent)  # type: ignore[arg-type]
        assert exc_info.value.status_code == expected_status

    assert (await chat_router.update_message(
        chat_router.UpdateMessageRequest(session_id="s1", message_id="m1", content="updated"),
        agent=agent,  # type: ignore[arg-type]
    ))["success"] is True
    for request, expected_status in [
        (chat_router.UpdateMessageRequest(session_id="s1", message_id="missing", content="x"), 404),
        (chat_router.UpdateMessageRequest(session_id="s1", message_id="bad", content="x"), 400),
        (chat_router.UpdateMessageRequest(session_id="s1", message_id="boom", content="x"), 500),
        (chat_router.UpdateMessageRequest(session_id="s1", message_id="m1", content="x", context_type="project"), 400),
    ]:
        with pytest.raises(HTTPException) as exc_info:
            await chat_router.update_message(request, agent=agent)  # type: ignore[arg-type]
        assert exc_info.value.status_code == expected_status

    assert (await chat_router.insert_separator(
        chat_router.InsertSeparatorRequest(session_id="s1"),
        agent=agent,  # type: ignore[arg-type]
    ))["message_id"] == "sep-1"
    assert (await chat_router.clear_all_messages(
        chat_router.ClearMessagesRequest(session_id="s1"),
        agent=agent,  # type: ignore[arg-type]
    ))["success"] is True

    for request, route, expected_status in [
        (chat_router.InsertSeparatorRequest(session_id="missing"), chat_router.insert_separator, 404),
        (chat_router.InsertSeparatorRequest(session_id="bad"), chat_router.insert_separator, 400),
        (chat_router.InsertSeparatorRequest(session_id="boom"), chat_router.insert_separator, 500),
        (chat_router.InsertSeparatorRequest(session_id="s1", context_type="project"), chat_router.insert_separator, 400),
        (chat_router.ClearMessagesRequest(session_id="missing"), chat_router.clear_all_messages, 404),
        (chat_router.ClearMessagesRequest(session_id="bad"), chat_router.clear_all_messages, 400),
        (chat_router.ClearMessagesRequest(session_id="boom"), chat_router.clear_all_messages, 500),
        (chat_router.ClearMessagesRequest(session_id="s1", context_type="project"), chat_router.clear_all_messages, 400),
    ]:
        with pytest.raises(HTTPException) as exc_info:
            await route(request, agent=agent)  # type: ignore[arg-type]
        assert exc_info.value.status_code == expected_status

    agent.compress_items = ["summary", {"type": "progress"}, {"type": "compression_complete"}]
    compress_response = await chat_router.compress_context(
        chat_router.CompressContextRequest(session_id="s1"),
        agent=agent,  # type: ignore[arg-type]
    )
    compress_payloads = await _collect_sse_payloads(compress_response)
    assert compress_payloads[0]["flow_event"]["event_type"] == "stream_started"
    assert compress_payloads[2]["flow_event"]["event_type"] == "stream_error"
    assert chat_router._is_terminal_payload(compress_payloads[-1]) is True

    agent.compress_error = FileNotFoundError()
    compress_response = await chat_router.compress_context(
        chat_router.CompressContextRequest(session_id="s1"),
        agent=agent,  # type: ignore[arg-type]
    )
    assert (await _collect_sse_payloads(compress_response))[-1]["flow_event"]["payload"]["error"] == "Session not found"

    agent.compress_error = ValueError("bad compress")
    compress_response = await chat_router.compress_context(
        chat_router.CompressContextRequest(session_id="s1"),
        agent=agent,  # type: ignore[arg-type]
    )
    assert (await _collect_sse_payloads(compress_response))[-1]["flow_event"]["payload"]["error"] == "bad compress"

    agent.compress_error = RuntimeError("compress boom")
    compress_response = await chat_router.compress_context(
        chat_router.CompressContextRequest(session_id="s1"),
        agent=agent,  # type: ignore[arg-type]
    )
    assert (await _collect_sse_payloads(compress_response))[-1]["flow_event"]["payload"]["error"] == "compress boom"

    with pytest.raises(HTTPException) as exc_info:
        await chat_router.compress_context(
            chat_router.CompressContextRequest(session_id="s1", context_type="project"),
            agent=agent,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    agent.compare_items = [{"model_id": "m1", "text": "hello"}]
    compare_response = await chat_router.chat_compare(
        chat_router.CompareRequest(session_id="s1", message="hi", model_ids=["m1", "m2"]),
        agent=agent,  # type: ignore[arg-type]
    )
    compare_payloads = await _collect_sse_payloads(compare_response)
    assert compare_payloads[0]["flow_event"]["event_type"] == "stream_started"
    assert chat_router._is_terminal_payload(compare_payloads[-1]) is True

    for request, expected_status in [
        (chat_router.CompareRequest(session_id="s1", message="hi", model_ids=["m1"]), 400),
        (chat_router.CompareRequest(session_id="s1", message="hi", model_ids=["m1", "m2"], context_type="project"), 400),
    ]:
        with pytest.raises(HTTPException) as exc_info:
            await chat_router.chat_compare(request, agent=agent)  # type: ignore[arg-type]
        assert exc_info.value.status_code == expected_status

    for error, expected_error in [
        (FileNotFoundError(), "Session not found"),
        (ValueError("bad compare"), "bad compare"),
        (RuntimeError("compare boom"), "compare boom"),
    ]:
        agent.compare_error = error
        compare_response = await chat_router.chat_compare(
            chat_router.CompareRequest(session_id="s1", message="hi", model_ids=["m1", "m2"]),
            agent=agent,  # type: ignore[arg-type]
        )
        assert (await _collect_sse_payloads(compare_response))[-1]["flow_event"]["payload"]["error"] == expected_error
