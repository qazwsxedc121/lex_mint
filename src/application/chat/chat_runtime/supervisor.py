"""Supervisor logic for committee orchestration."""

from collections.abc import Awaitable, Callable

from .committee_types import CommitteeDecision, CommitteeRuntimeState
from .supervisor_gatekeeper import (
    CommitteeSupervisorDecisionGatekeeper,
    CommitteeSupervisorGatekeeperConfig,
)
from .supervisor_parser import CommitteeSupervisorDecisionParser
from .supervisor_prompts import (
    CommitteeSupervisorPromptBuilder,
    CommitteeSupervisorPromptConfig,
)

DecisionLLMCaller = Callable[[str, str], Awaitable[str]]


class CommitteeSupervisor:
    """Asks the supervisor model to choose between `speak` and `finish`."""

    def __init__(
        self,
        *,
        supervisor_id: str,
        supervisor_name: str,
        participant_order: list[str],
        participant_names: dict[str, str],
        max_rounds: int,
        min_member_turns_before_finish: int = 2,
        min_total_rounds_before_finish: int = 0,
        max_parallel_speakers: int = 3,
        allow_parallel_speak: bool = True,
        allow_finish: bool = True,
        supervisor_system_prompt_template: str | None = None,
        summary_instruction_template: str | None = None,
    ):
        self.supervisor_id = supervisor_id
        self.supervisor_name = supervisor_name
        self.participant_order = participant_order
        self.participant_names = participant_names
        self.max_rounds = max_rounds
        self.min_member_turns_before_finish = max(1, int(min_member_turns_before_finish))
        self.min_total_rounds_before_finish = max(0, int(min_total_rounds_before_finish))
        self.max_parallel_speakers = max(1, int(max_parallel_speakers))
        self.allow_parallel_speak = bool(allow_parallel_speak)
        self.allow_finish = bool(allow_finish)
        self.supervisor_system_prompt_template = (
            supervisor_system_prompt_template.strip()
            if isinstance(supervisor_system_prompt_template, str)
            and supervisor_system_prompt_template.strip()
            else None
        )
        self.summary_instruction_template = (
            summary_instruction_template.strip()
            if isinstance(summary_instruction_template, str)
            and summary_instruction_template.strip()
            else None
        )

        self._prompt_builder = CommitteeSupervisorPromptBuilder(
            CommitteeSupervisorPromptConfig(
                supervisor_id=self.supervisor_id,
                participant_order=list(self.participant_order),
                participant_names=dict(self.participant_names),
                max_rounds=self.max_rounds,
                min_member_turns_before_finish=self.min_member_turns_before_finish,
                min_total_rounds_before_finish=self.min_total_rounds_before_finish,
                max_parallel_speakers=self.max_parallel_speakers,
                allow_parallel_speak=self.allow_parallel_speak,
                allow_finish=self.allow_finish,
                supervisor_system_prompt_template=self.supervisor_system_prompt_template,
                summary_instruction_template=self.summary_instruction_template,
            )
        )
        self._decision_parser = CommitteeSupervisorDecisionParser()
        self._decision_gatekeeper = CommitteeSupervisorDecisionGatekeeper(
            CommitteeSupervisorGatekeeperConfig(
                supervisor_id=self.supervisor_id,
                participant_order=list(self.participant_order),
                max_rounds=self.max_rounds,
                min_member_turns_before_finish=self.min_member_turns_before_finish,
                min_total_rounds_before_finish=self.min_total_rounds_before_finish,
                max_parallel_speakers=self.max_parallel_speakers,
                allow_parallel_speak=self.allow_parallel_speak,
                allow_finish=self.allow_finish,
            )
        )

    async def decide(
        self,
        state: CommitteeRuntimeState,
        llm_caller: DecisionLLMCaller,
    ) -> CommitteeDecision:
        """Return the next action by calling supervisor LLM and normalizing output."""
        if state.round_index >= self.max_rounds:
            return CommitteeDecision(action="finish", reason="max_rounds_reached")

        valid_targets = [
            assistant_id
            for assistant_id in self.participant_order
            if assistant_id in state.participants
        ]
        required_targets = self._decision_gatekeeper.required_member_targets(valid_targets)

        system_prompt = self._prompt_builder.build_system_prompt()
        user_prompt = self._prompt_builder.build_user_prompt(
            state,
            required_targets=required_targets,
        )
        raw_output = await llm_caller(system_prompt, user_prompt)

        decision = self._decision_parser.parse(raw_output)
        return self._decision_gatekeeper.normalize(decision, state)

    def build_summary_instruction(
        self,
        state: CommitteeRuntimeState,
        *,
        reason: str,
        draft_summary: str | None = None,
    ) -> str:
        """Build the final summary instruction for the supervisor assistant."""
        return self._prompt_builder.build_summary_instruction(
            state,
            reason=reason,
            draft_summary=draft_summary,
        )
