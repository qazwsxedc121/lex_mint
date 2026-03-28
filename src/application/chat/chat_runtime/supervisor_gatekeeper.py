"""Decision normalization and gating for committee supervisor actions."""

from __future__ import annotations

from dataclasses import dataclass

from .committee_types import CommitteeDecision, CommitteeRuntimeState


@dataclass(frozen=True)
class CommitteeSupervisorGatekeeperConfig:
    """Static policy used to normalize supervisor decisions."""

    supervisor_id: str
    participant_order: list[str]
    max_rounds: int
    min_member_turns_before_finish: int
    min_total_rounds_before_finish: int
    max_parallel_speakers: int
    allow_parallel_speak: bool
    allow_finish: bool


class CommitteeSupervisorDecisionGatekeeper:
    """Applies coverage/depth/validity rules to supervisor decisions."""

    def __init__(self, config: CommitteeSupervisorGatekeeperConfig):
        self.config = config

    def normalize(
        self,
        decision: CommitteeDecision,
        state: CommitteeRuntimeState,
    ) -> CommitteeDecision:
        valid_targets = [
            assistant_id
            for assistant_id in self.config.participant_order
            if assistant_id in state.participants
        ]
        if not valid_targets:
            return CommitteeDecision(action="finish", reason="no_valid_participants")

        pending_member_targets = self._pending_member_targets(state, valid_targets)
        required_targets = self.required_member_targets(valid_targets)
        depth_target = self.depth_required_target(state, required_targets)

        if decision.action == "parallel_speak" and not self.config.allow_parallel_speak:
            decision.action = "speak"
            decision.reason = decision.reason or "parallel_speak_disabled"
            if not decision.assistant_id and decision.assistant_ids:
                decision.assistant_id = decision.assistant_ids[0]
            decision.assistant_ids = None

        if decision.action == "finish":
            if not self.config.allow_finish:
                forced_target = pending_member_targets[0] if pending_member_targets else None
                if not forced_target:
                    forced_target = depth_target or self._fallback_speaker(state, valid_targets)
                return self._build_forced_speak_decision(
                    state=state,
                    assistant_id=forced_target,
                    reason="finish_disabled",
                    depth_target=depth_target,
                )
            if pending_member_targets:
                forced_target = pending_member_targets[0]
                return self._build_forced_speak_decision(
                    state=state,
                    assistant_id=forced_target,
                    reason="coverage_required_before_finish",
                )
            if depth_target:
                return self._build_forced_speak_decision(
                    state=state,
                    assistant_id=depth_target,
                    reason="discussion_depth_required_before_finish",
                    depth_target=depth_target,
                )
            if not decision.reason:
                decision.reason = "supervisor_finish"
            return decision

        if decision.action == "parallel_speak":
            remaining_rounds = max(self.config.max_rounds - state.round_index, 0)
            requested_targets = list(decision.assistant_ids or [])
            if not requested_targets and decision.assistant_id:
                requested_targets = [decision.assistant_id]

            selected_targets: list[str] = []
            for assistant_id in requested_targets:
                if assistant_id not in valid_targets or assistant_id == self.config.supervisor_id:
                    continue
                if assistant_id in selected_targets:
                    continue
                selected_targets.append(assistant_id)

            if pending_member_targets:
                for assistant_id in pending_member_targets:
                    if assistant_id not in selected_targets:
                        selected_targets.append(assistant_id)

            if depth_target and depth_target not in selected_targets:
                selected_targets.append(depth_target)

            required_slots = 1
            if (
                pending_member_targets
                and len(pending_member_targets) > 1
                and remaining_rounds <= len(pending_member_targets)
            ):
                required_slots = 2

            max_parallel_targets = self.config.max_parallel_speakers
            selected_targets = selected_targets[:max_parallel_targets]
            if len(selected_targets) < required_slots:
                for assistant_id in self.required_member_targets(valid_targets):
                    if assistant_id not in selected_targets:
                        selected_targets.append(assistant_id)
                    if len(selected_targets) >= required_slots:
                        break

            if len(selected_targets) <= 1:
                fallback_target = selected_targets[0] if selected_targets else None
                if not fallback_target:
                    fallback_target = (
                        pending_member_targets[0]
                        if pending_member_targets
                        else self._fallback_speaker(state, valid_targets)
                    )
                decision.action = "speak"
                decision.assistant_id = fallback_target
                decision.assistant_ids = None
                decision.reason = decision.reason or "parallel_fallback_speaker"
                if not decision.instruction:
                    target_name = state.participants.get(fallback_target, fallback_target)
                    decision.instruction = f"Please contribute your best analysis as {target_name}."
                return decision

            decision.assistant_ids = selected_targets
            decision.assistant_id = selected_targets[0]
            if not decision.reason:
                decision.reason = "supervisor_selected_parallel_speakers"
            if not decision.instruction:
                decision.instruction = "Provide your perspective with concrete points, and avoid repeating other members verbatim."
            return decision

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

    def required_member_targets(self, valid_targets: list[str]) -> list[str]:
        return [
            assistant_id
            for assistant_id in self.config.participant_order
            if assistant_id in valid_targets and assistant_id != self.config.supervisor_id
        ]

    def depth_required_target(
        self,
        state: CommitteeRuntimeState,
        required_targets: list[str],
    ) -> str | None:
        """Return the next member that should speak to satisfy long-discussion depth."""
        if not required_targets:
            return None

        counts = self.member_turn_counts(state, required_targets)
        under_min = [
            assistant_id
            for assistant_id in required_targets
            if counts.get(assistant_id, 0) < self.config.min_member_turns_before_finish
        ]
        if not under_min and state.round_index >= self.config.min_total_rounds_before_finish:
            return None

        candidates = under_min if under_min else required_targets
        last_speaker = state.turns[-1].assistant_id if state.turns else None

        ranked = sorted(
            candidates,
            key=lambda assistant_id: (
                counts.get(assistant_id, 0),
                self.config.participant_order.index(assistant_id)
                if assistant_id in self.config.participant_order
                else 10_000,
            ),
        )
        for assistant_id in ranked:
            if assistant_id != last_speaker:
                return assistant_id
        return ranked[0] if ranked else None

    @staticmethod
    def member_turn_counts(
        state: CommitteeRuntimeState,
        required_targets: list[str],
    ) -> dict[str, int]:
        counts: dict[str, int] = dict.fromkeys(required_targets, 0)
        for turn in state.turns:
            if turn.assistant_id in counts:
                counts[turn.assistant_id] += 1
        return counts

    def _build_forced_speak_decision(
        self,
        *,
        state: CommitteeRuntimeState,
        assistant_id: str,
        reason: str,
        depth_target: str | None = None,
    ) -> CommitteeDecision:
        assistant_name = state.participants.get(assistant_id, assistant_id)
        if depth_target and assistant_id == depth_target:
            instruction = f"As {assistant_name}, build on prior points, add new evidence, and sharpen trade-offs."
        else:
            instruction = f"Please contribute your best analysis as {assistant_name}."
        return CommitteeDecision(
            action="speak",
            assistant_id=assistant_id,
            instruction=instruction,
            reason=reason,
        )

    def _fallback_speaker(self, state: CommitteeRuntimeState, valid_targets: list[str]) -> str:
        non_supervisor = [
            assistant_id
            for assistant_id in valid_targets
            if assistant_id != self.config.supervisor_id
        ]
        candidates = non_supervisor if non_supervisor else valid_targets
        fallback_index = len(state.turns) % len(candidates)
        return candidates[fallback_index]

    def _pending_member_targets(
        self,
        state: CommitteeRuntimeState,
        valid_targets: list[str],
    ) -> list[str]:
        required_targets = self.required_member_targets(valid_targets)
        spoken_targets = {turn.assistant_id for turn in state.turns}
        return [
            assistant_id for assistant_id in required_targets if assistant_id not in spoken_targets
        ]
