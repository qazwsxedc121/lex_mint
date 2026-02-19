"""Supervisor logic for committee-style group orchestration."""

import json
import re
from typing import Awaitable, Callable, Dict, List, Optional

from .types import CommitteeDecision, CommitteeRuntimeState


DecisionLLMCaller = Callable[[str, str], Awaitable[str]]


class CommitteeSupervisor:
    """Asks the supervisor model to choose between `speak` and `finish`."""

    def __init__(
        self,
        *,
        supervisor_id: str,
        supervisor_name: str,
        participant_order: List[str],
        participant_names: Dict[str, str],
        max_rounds: int,
        min_member_turns_before_finish: int = 2,
        min_total_rounds_before_finish: int = 0,
    ):
        self.supervisor_id = supervisor_id
        self.supervisor_name = supervisor_name
        self.participant_order = participant_order
        self.participant_names = participant_names
        self.max_rounds = max_rounds
        self.min_member_turns_before_finish = max(1, int(min_member_turns_before_finish))
        self.min_total_rounds_before_finish = max(0, int(min_total_rounds_before_finish))

    async def decide(
        self,
        state: CommitteeRuntimeState,
        llm_caller: DecisionLLMCaller,
    ) -> CommitteeDecision:
        """Return the next action by calling supervisor LLM and normalizing output."""
        if state.round_index >= self.max_rounds:
            return CommitteeDecision(action="finish", reason="max_rounds_reached")

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(state)
        raw_output = await llm_caller(system_prompt, user_prompt)

        decision = self._parse_decision(raw_output)
        return self._normalize_decision(decision, state)

    def build_summary_instruction(
        self,
        state: CommitteeRuntimeState,
        *,
        reason: str,
        draft_summary: Optional[str] = None,
    ) -> str:
        """Build the final summary instruction for the supervisor assistant."""
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
        return (
            f"Committee orchestration is ending (reason: {reason}).\n"
            "Please provide a concise, user-facing final answer that synthesizes member viewpoints.\n"
            "Include concrete recommendations and clearly state trade-offs when relevant.\n"
            f"{draft_block}\n"
            "Member turn highlights:\n"
            f"{turns_block}"
        )

    def _build_system_prompt(self) -> str:
        return (
            "You are the committee supervisor in a multi-assistant discussion.\n"
            "Decide one action for the next step and return JSON only.\n"
            "Allowed actions:\n"
            "1) speak -> pick one assistant to speak next.\n"
            "2) finish -> end discussion and request final synthesis.\n\n"
            "JSON schema:\n"
            "{\n"
            '  "action": "speak" | "finish",\n'
            '  "assistant_id": "required when action=speak",\n'
            '  "instruction": "optional instruction for the selected assistant",\n'
            '  "reason": "short rationale",\n'
            '  "final_response": "optional draft final response when action=finish"\n'
            "}\n"
            "Rules:\n"
            "- Use only provided assistant_id values.\n"
            "- Prefer concise instruction text.\n"
            "- Return strict JSON with no markdown."
        )

    def _build_user_prompt(self, state: CommitteeRuntimeState) -> str:
        participants = []
        for index, assistant_id in enumerate(self.participant_order, start=1):
            name = self.participant_names.get(assistant_id, assistant_id)
            marker = " (supervisor)" if assistant_id == self.supervisor_id else ""
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
        remaining = max(self.max_rounds - state.round_index, 0)
        required_targets = self._required_member_targets(list(state.participants.keys()))
        member_counts = self._member_turn_counts(state, required_targets)
        count_lines = []
        for target in required_targets:
            name = state.participants.get(target, target)
            count = member_counts.get(target, 0)
            count_lines.append(
                f"- {name} [{target}]: {count}/{self.min_member_turns_before_finish} turns"
            )
        count_block = "\n".join(count_lines) if count_lines else "- no member constraints"

        return (
            f"User request:\n{state.user_message}\n\n"
            "Participants:\n"
            f"{participant_block}\n\n"
            f"Completed rounds: {state.round_index}\n"
            f"Remaining rounds before forced finish: {remaining}\n\n"
            "Completion gates:\n"
            f"- Minimum total rounds before finish: {self.min_total_rounds_before_finish}\n"
            f"- Minimum turns per non-supervisor member: {self.min_member_turns_before_finish}\n"
            "Member turn progress:\n"
            f"{count_block}\n\n"
            "Discussion so far:\n"
            f"{turn_block}\n\n"
            "Return one next action in JSON."
        )

    def _parse_decision(self, raw_output: str) -> CommitteeDecision:
        payload = self._extract_json_payload(raw_output)
        if not payload:
            return CommitteeDecision(action="speak", reason="invalid_supervisor_output")

        action_raw = str(payload.get("action", "")).strip().lower()
        action_map = {
            "speak": "speak",
            "call_agent": "speak",
            "ask_member": "speak",
            "finish": "finish",
            "end": "finish",
            "done": "finish",
        }
        action = action_map.get(action_raw, "speak")

        assistant_id = payload.get("assistant_id") or payload.get("agent_id")
        instruction = payload.get("instruction")
        reason = payload.get("reason") or ""
        final_response = payload.get("final_response") or payload.get("summary")

        return CommitteeDecision(
            action=action,  # type: ignore[arg-type]
            assistant_id=str(assistant_id).strip() if assistant_id else None,
            instruction=str(instruction).strip() if instruction else None,
            reason=str(reason).strip(),
            final_response=str(final_response).strip() if final_response else None,
        )

    @staticmethod
    def _extract_json_payload(raw_output: str) -> Optional[Dict]:
        text = (raw_output or "").strip()
        if not text:
            return None

        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text, re.IGNORECASE)
        candidates = [fenced.group(1)] if fenced else []
        candidates.append(text)

        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidates.append(text[start_idx:end_idx + 1])

        for candidate in candidates:
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
        return None

    def _normalize_decision(
        self,
        decision: CommitteeDecision,
        state: CommitteeRuntimeState,
    ) -> CommitteeDecision:
        valid_targets = [
            assistant_id
            for assistant_id in self.participant_order
            if assistant_id in state.participants
        ]
        if not valid_targets:
            return CommitteeDecision(action="finish", reason="no_valid_participants")

        pending_member_targets = self._pending_member_targets(state, valid_targets)
        required_targets = self._required_member_targets(valid_targets)
        depth_target = self._depth_required_target(state, required_targets)
        if decision.action == "finish":
            if pending_member_targets:
                forced_target = pending_member_targets[0]
                forced_name = state.participants.get(forced_target, forced_target)
                return CommitteeDecision(
                    action="speak",
                    assistant_id=forced_target,
                    instruction=f"Please contribute your best analysis as {forced_name}.",
                    reason="coverage_required_before_finish",
                )
            if depth_target:
                forced_name = state.participants.get(depth_target, depth_target)
                return CommitteeDecision(
                    action="speak",
                    assistant_id=depth_target,
                    instruction=(
                        f"As {forced_name}, build on prior points, add new evidence, and sharpen trade-offs."
                    ),
                    reason="discussion_depth_required_before_finish",
                )
            if not decision.reason:
                decision.reason = "supervisor_finish"
            return decision

        # Normalize speak target
        preferred_target = decision.assistant_id
        if pending_member_targets and preferred_target not in pending_member_targets:
            preferred_target = pending_member_targets[0]
            decision.reason = decision.reason or "coverage_first_speaker"
        elif depth_target and preferred_target != depth_target:
            preferred_target = depth_target
            decision.reason = decision.reason or "discussion_depth_balance"
        elif preferred_target not in valid_targets:
            preferred_target = self._fallback_speaker(state, valid_targets)
            decision.reason = decision.reason or "fallback_speaker"

        decision.assistant_id = preferred_target
        if not decision.instruction:
            target_name = state.participants.get(preferred_target, preferred_target)
            decision.instruction = f"Please contribute your best analysis as {target_name}."
        if not decision.reason:
            decision.reason = "supervisor_selected_speaker"
        return decision

    def _fallback_speaker(self, state: CommitteeRuntimeState, valid_targets: List[str]) -> str:
        non_supervisor = [assistant_id for assistant_id in valid_targets if assistant_id != self.supervisor_id]
        candidates = non_supervisor if non_supervisor else valid_targets
        fallback_index = len(state.turns) % len(candidates)
        return candidates[fallback_index]

    def _required_member_targets(self, valid_targets: List[str]) -> List[str]:
        return [
            assistant_id
            for assistant_id in self.participant_order
            if assistant_id in valid_targets and assistant_id != self.supervisor_id
        ]

    def _pending_member_targets(
        self,
        state: CommitteeRuntimeState,
        valid_targets: List[str],
    ) -> List[str]:
        required_targets = self._required_member_targets(valid_targets)
        spoken_targets = {turn.assistant_id for turn in state.turns}
        return [assistant_id for assistant_id in required_targets if assistant_id not in spoken_targets]

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

    def _depth_required_target(
        self,
        state: CommitteeRuntimeState,
        required_targets: List[str],
    ) -> Optional[str]:
        """Return the next member that should speak to satisfy long-discussion depth."""
        if not required_targets:
            return None

        counts = self._member_turn_counts(state, required_targets)
        under_min = [
            assistant_id
            for assistant_id in required_targets
            if counts.get(assistant_id, 0) < self.min_member_turns_before_finish
        ]
        if not under_min and state.round_index >= self.min_total_rounds_before_finish:
            return None

        candidates = under_min if under_min else required_targets
        last_speaker = state.turns[-1].assistant_id if state.turns else None

        ranked = sorted(
            candidates,
            key=lambda assistant_id: (
                counts.get(assistant_id, 0),
                self.participant_order.index(assistant_id)
                if assistant_id in self.participant_order
                else 10_000,
            ),
        )
        for assistant_id in ranked:
            if assistant_id != last_speaker:
                return assistant_id
        return ranked[0] if ranked else None
