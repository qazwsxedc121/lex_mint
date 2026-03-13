"""Prompt builders for committee supervisor decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .committee_types import CommitteeRuntimeState


@dataclass(frozen=True)
class CommitteeSupervisorPromptConfig:
    """Static prompt configuration for one supervisor instance."""

    supervisor_id: str
    participant_order: List[str]
    participant_names: Dict[str, str]
    max_rounds: int
    min_member_turns_before_finish: int
    min_total_rounds_before_finish: int
    max_parallel_speakers: int
    allow_parallel_speak: bool
    allow_finish: bool
    supervisor_system_prompt_template: Optional[str] = None
    summary_instruction_template: Optional[str] = None


class CommitteeSupervisorPromptBuilder:
    """Builds system, user, and summary prompts for committee supervision."""

    def __init__(self, config: CommitteeSupervisorPromptConfig):
        self.config = config

    def build_system_prompt(self) -> str:
        if self.config.supervisor_system_prompt_template:
            return self.config.supervisor_system_prompt_template

        allowed_actions = ["speak"]
        if self.config.allow_parallel_speak:
            allowed_actions.append("parallel_speak")
        if self.config.allow_finish:
            allowed_actions.append("finish")
        allowed_actions_text = " | ".join(f'"{action}"' for action in allowed_actions)
        parallel_rule = (
            f"- Keep parallel_speak target count small (2-{self.config.max_parallel_speakers}).\n"
            if self.config.allow_parallel_speak
            else "- parallel_speak is disabled for this session.\n"
        )
        finish_rule = (
            "- finish is allowed only when completion gates are satisfied.\n"
            if self.config.allow_finish
            else "- finish is disabled for this session.\n"
        )

        return (
            "You are the committee supervisor in a multi-assistant discussion.\n"
            "Decide one action for the next step and return JSON only.\n"
            "Allowed actions:\n"
            "1) speak -> pick one assistant to speak next.\n"
            "2) parallel_speak -> pick multiple assistants to speak in parallel this round.\n"
            "3) finish -> end discussion and request final synthesis.\n\n"
            "JSON schema:\n"
            "{\n"
            f'  "action": {allowed_actions_text},\n'
            '  "assistant_id": "required when action=speak",\n'
            '  "assistant_ids": "required when action=parallel_speak",\n'
            '  "instruction": "optional instruction for the selected assistant",\n'
            '  "reason": "short rationale",\n'
            '  "final_response": "optional draft final response when action=finish"\n'
            "}\n"
            "Rules:\n"
            "- Use only provided assistant_id values.\n"
            f"{parallel_rule}"
            f"{finish_rule}"
            "- Prefer concise instruction text.\n"
            "- Return strict JSON with no markdown."
        )

    def build_user_prompt(
        self,
        state: CommitteeRuntimeState,
        *,
        required_targets: List[str],
    ) -> str:
        participants = []
        for index, assistant_id in enumerate(self.config.participant_order, start=1):
            name = self.config.participant_names.get(assistant_id, assistant_id)
            marker = " (supervisor)" if assistant_id == self.config.supervisor_id else ""
            participants.append(f"{index}. {name} [{assistant_id}]{marker}")

        turn_lines: List[str] = []
        for index, turn in enumerate(state.turns, start=1):
            key_points = "; ".join(turn.key_points[:2]) if turn.key_points else turn.content_preview
            risks = "; ".join(turn.risks[:1]) if turn.risks else ""
            actions = "; ".join(turn.actions[:1]) if turn.actions else ""
            extra_parts = []
            if risks:
                extra_parts.append(f"risk={risks}")
            if actions:
                extra_parts.append(f"next={actions}")
            extra = f" ({' | '.join(extra_parts)})" if extra_parts else ""
            turn_lines.append(
                f"{index}. {turn.assistant_name} [{turn.assistant_id}]: {key_points}{extra}"
            )

        turn_block = "\n".join(turn_lines) if turn_lines else "- No member has spoken yet."
        participant_block = "\n".join(participants) if participants else "- none"
        remaining = max(self.config.max_rounds - state.round_index, 0)
        member_counts = self._member_turn_counts(state, required_targets)
        count_lines = []
        for target in required_targets:
            name = state.participants.get(target, target)
            count = member_counts.get(target, 0)
            count_lines.append(
                f"- {name} [{target}]: {count}/{self.config.min_member_turns_before_finish} turns"
            )
        count_block = "\n".join(count_lines) if count_lines else "- no member constraints"

        return (
            f"User request:\n{state.user_message}\n\n"
            "Participants:\n"
            f"{participant_block}\n\n"
            f"Completed rounds: {state.round_index}\n"
            f"Remaining rounds before forced finish: {remaining}\n\n"
            "Completion gates:\n"
            f"- Minimum total rounds before finish: {self.config.min_total_rounds_before_finish}\n"
            f"- Minimum turns per non-supervisor member: {self.config.min_member_turns_before_finish}\n"
            "Member turn progress:\n"
            f"{count_block}\n\n"
            "Discussion so far:\n"
            f"{turn_block}\n\n"
            "Return one next action in JSON."
        )

    def build_summary_instruction(
        self,
        state: CommitteeRuntimeState,
        *,
        reason: str,
        draft_summary: Optional[str] = None,
    ) -> str:
        lines: List[str] = []
        for index, turn in enumerate(state.turns, start=1):
            key_points = "; ".join(turn.key_points[:3]) if turn.key_points else turn.content_preview
            risks = "; ".join(turn.risks[:2]) if turn.risks else ""
            actions = "; ".join(turn.actions[:2]) if turn.actions else ""
            notes: List[str] = []
            if risks:
                notes.append(f"risks={risks}")
            if actions:
                notes.append(f"actions={actions}")
            notes_block = f" ({' | '.join(notes)})" if notes else ""
            lines.append(
                f"{index}. {turn.assistant_name} [{turn.assistant_id}]: {key_points}{notes_block}"
            )
        turns_block = "\n".join(lines) if lines else "- No member turns recorded."
        draft_block = f"\nDraft summary from supervisor decision:\n{draft_summary}\n" if draft_summary else ""
        if self.config.summary_instruction_template:
            try:
                return self.config.summary_instruction_template.format(
                    reason=reason,
                    user_message=state.user_message,
                    draft_summary=(draft_summary or ""),
                    turns_block=turns_block,
                )
            except Exception:
                pass
        return (
            f"Committee orchestration is ending (reason: {reason}).\n"
            "Please provide a concise, user-facing final answer that synthesizes member viewpoints.\n"
            "Include concrete recommendations and clearly state trade-offs when relevant.\n"
            f"{draft_block}\n"
            "Member turn highlights:\n"
            f"{turns_block}"
        )

    @staticmethod
    def _member_turn_counts(
        state: CommitteeRuntimeState,
        required_targets: List[str],
    ) -> Dict[str, int]:
        counts: Dict[str, int] = {assistant_id: 0 for assistant_id in required_targets}
        for turn in state.turns:
            if turn.assistant_id in counts:
                counts[turn.assistant_id] += 1
        return counts
