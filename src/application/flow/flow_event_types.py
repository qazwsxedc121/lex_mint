"""Canonical FlowEvent type constants."""

from __future__ import annotations

from typing import Final, FrozenSet


STREAM_STARTED: Final[str] = "stream_started"
STREAM_ENDED: Final[str] = "stream_ended"
STREAM_ERROR: Final[str] = "stream_error"
RESUME_STARTED: Final[str] = "resume_started"
REPLAY_FINISHED: Final[str] = "replay_finished"

TEXT_DELTA: Final[str] = "text_delta"
REASONING_DURATION_REPORTED: Final[str] = "reasoning_duration_reported"

TOOL_CALL_STARTED: Final[str] = "tool_call_started"
TOOL_CALL_FINISHED: Final[str] = "tool_call_finished"
TOOL_DIAGNOSTICS_REPORTED: Final[str] = "tool_diagnostics_reported"

ASSISTANT_TURN_STARTED: Final[str] = "assistant_turn_started"
ASSISTANT_TURN_FINISHED: Final[str] = "assistant_turn_finished"
GROUP_ROUND_STARTED: Final[str] = "group_round_started"
GROUP_ACTION_REPORTED: Final[str] = "group_action_reported"
GROUP_DONE_REPORTED: Final[str] = "group_done_reported"
COMPARE_MODEL_STARTED: Final[str] = "compare_model_started"
COMPARE_MODEL_FINISHED: Final[str] = "compare_model_finished"
COMPARE_MODEL_FAILED: Final[str] = "compare_model_failed"
COMPARE_COMPLETED: Final[str] = "compare_completed"

USAGE_REPORTED: Final[str] = "usage_reported"
SOURCES_REPORTED: Final[str] = "sources_reported"
CONTEXT_REPORTED: Final[str] = "context_reported"
USER_MESSAGE_IDENTIFIED: Final[str] = "user_message_identified"
ASSISTANT_MESSAGE_IDENTIFIED: Final[str] = "assistant_message_identified"
FOLLOWUP_QUESTIONS_REPORTED: Final[str] = "followup_questions_reported"
LANGUAGE_DETECTED: Final[str] = "language_detected"
TRANSLATION_COMPLETED: Final[str] = "translation_completed"
COMPRESSION_COMPLETED: Final[str] = "compression_completed"
WORKFLOW_RUN_STARTED: Final[str] = "workflow_run_started"
WORKFLOW_NODE_STARTED: Final[str] = "workflow_node_started"
WORKFLOW_NODE_RETRYING: Final[str] = "workflow_node_retrying"
WORKFLOW_NODE_FINISHED: Final[str] = "workflow_node_finished"
WORKFLOW_CONDITION_EVALUATED: Final[str] = "workflow_condition_evaluated"
WORKFLOW_OUTPUT_REPORTED: Final[str] = "workflow_output_reported"
WORKFLOW_ARTIFACT_WRITTEN: Final[str] = "workflow_artifact_written"
WORKFLOW_RUN_FINISHED: Final[str] = "workflow_run_finished"

TERMINAL_EVENT_TYPES: Final[FrozenSet[str]] = frozenset(
    {
        STREAM_ENDED,
        STREAM_ERROR,
    }
)
