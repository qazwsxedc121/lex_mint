"""Group-chat settings normalization and committee defaults resolver."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .policy import CommitteePolicy


ResolveRoundPolicy = Callable[..., Dict[str, int]]


@dataclass(frozen=True)
class ResolvedCommitteeSettings:
    """Fully-resolved committee settings used by runtime/supervisor."""

    supervisor_id: str
    max_rounds: int
    min_member_turns_before_finish: int
    min_total_rounds_before_finish: int
    max_parallel_speakers: int
    role_retry_limit: int
    allow_parallel_speak: bool = True
    allow_finish: bool = True
    supervisor_system_prompt_template: Optional[str] = None
    summary_instruction_template: Optional[str] = None
    fallback_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize resolved committee settings for API/debug responses."""
        return {
            "supervisor_id": self.supervisor_id,
            "policy": {
                "max_rounds": self.max_rounds,
                "min_member_turns_before_finish": self.min_member_turns_before_finish,
                "min_total_rounds_before_finish": self.min_total_rounds_before_finish,
                "max_parallel_speakers": self.max_parallel_speakers,
                "role_retry_limit": self.role_retry_limit,
            },
            "actions": {
                "allow_parallel_speak": self.allow_parallel_speak,
                "allow_finish": self.allow_finish,
            },
            "prompting": {
                "supervisor_system_prompt_template": self.supervisor_system_prompt_template,
                "summary_instruction_template": self.summary_instruction_template,
            },
            "fallback_notes": list(self.fallback_notes),
        }


@dataclass(frozen=True)
class ResolvedGroupSettings:
    """Resolved group-level settings for one session execution."""

    group_mode: str
    group_assistants: List[str]
    group_settings: Dict[str, Any]
    committee: Optional[ResolvedCommitteeSettings] = None

    def to_effective_dict(self) -> Dict[str, Any]:
        """Serialize effective group settings for API responses."""
        result: Dict[str, Any] = {
            "group_mode": self.group_mode,
            "group_assistants": list(self.group_assistants),
        }
        if self.committee is not None:
            result["committee"] = self.committee.to_dict()
        return result


class GroupSettingsResolver:
    """Normalize session group settings and resolve runtime committee values."""

    ALLOWED_GROUP_MODES = {"round_robin", "committee"}
    _MAX_ROUNDS_HARD_CAP = 24
    _MAX_PARALLEL_SPEAKERS_CAP = 5
    _ROLE_RETRY_LIMIT_CAP = 4

    @staticmethod
    def normalize_group_mode(
        group_mode: Optional[str],
        *,
        group_assistants: Optional[List[str]],
    ) -> Optional[str]:
        """Normalize group mode while keeping backward-compatible defaults."""
        if group_mode is None:
            return "round_robin" if group_assistants else None

        normalized = str(group_mode).strip().lower()
        if normalized not in GroupSettingsResolver.ALLOWED_GROUP_MODES:
            return None
        if not group_assistants:
            return None
        return normalized

    @staticmethod
    def normalize_group_settings(raw_group_settings: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize user-provided group settings into a stable schema."""
        payload = raw_group_settings if isinstance(raw_group_settings, dict) else {}
        result: Dict[str, Any] = {"version": 1}

        committee_raw = payload.get("committee")
        if isinstance(committee_raw, dict):
            committee: Dict[str, Any] = {}

            supervisor_id = committee_raw.get("supervisor_id")
            if isinstance(supervisor_id, str) and supervisor_id.strip():
                committee["supervisor_id"] = supervisor_id.strip()

            policy_raw = committee_raw.get("policy")
            policy: Dict[str, Any] = {}
            if isinstance(policy_raw, dict):
                for key in (
                    "max_rounds",
                    "min_member_turns_before_finish",
                    "min_total_rounds_before_finish",
                    "max_parallel_speakers",
                    "role_retry_limit",
                ):
                    value = GroupSettingsResolver._coerce_int(policy_raw.get(key))
                    if value is not None:
                        policy[key] = value
            if policy:
                committee["policy"] = policy

            actions_raw = committee_raw.get("actions")
            actions: Dict[str, Any] = {}
            if isinstance(actions_raw, dict):
                for key in ("allow_parallel_speak", "allow_finish"):
                    value = actions_raw.get(key)
                    if isinstance(value, bool):
                        actions[key] = value
            if actions:
                committee["actions"] = actions

            prompting_raw = committee_raw.get("prompting")
            prompting: Dict[str, Any] = {}
            if isinstance(prompting_raw, dict):
                for key in ("supervisor_system_prompt_template", "summary_instruction_template"):
                    value = prompting_raw.get(key)
                    if isinstance(value, str) and value.strip():
                        prompting[key] = value.strip()
            if prompting:
                committee["prompting"] = prompting

            if committee:
                result["committee"] = committee

        round_robin_raw = payload.get("round_robin")
        if isinstance(round_robin_raw, dict):
            # Keep as extension point; no effective policy fields yet.
            result["round_robin"] = {}

        return result

    @classmethod
    def resolve(
        cls,
        *,
        group_mode: Optional[str],
        group_assistants: List[str],
        group_settings: Optional[Dict[str, Any]],
        assistant_config_map: Dict[str, Any],
        resolve_round_policy: Optional[ResolveRoundPolicy] = None,
    ) -> ResolvedGroupSettings:
        """Resolve effective runtime settings for one group chat session."""
        normalized_mode = cls.normalize_group_mode(group_mode, group_assistants=group_assistants)
        if not normalized_mode:
            normalized_mode = "round_robin" if group_assistants else "round_robin"

        normalized_settings = cls.normalize_group_settings(group_settings)
        committee_settings: Optional[ResolvedCommitteeSettings] = None
        if normalized_mode == "committee":
            committee_settings = cls.resolve_committee_settings(
                group_assistants=group_assistants,
                group_settings=normalized_settings,
                assistant_config_map=assistant_config_map,
                resolve_round_policy=resolve_round_policy,
            )

        return ResolvedGroupSettings(
            group_mode=normalized_mode,
            group_assistants=list(group_assistants),
            group_settings=normalized_settings,
            committee=committee_settings,
        )

    @classmethod
    def resolve_committee_settings(
        cls,
        *,
        group_assistants: List[str],
        group_settings: Dict[str, Any],
        assistant_config_map: Dict[str, Any],
        resolve_round_policy: Optional[ResolveRoundPolicy] = None,
    ) -> ResolvedCommitteeSettings:
        """Resolve committee policy, actions, and prompt templates with defaults."""
        if not group_assistants:
            raise ValueError("group_assistants cannot be empty when resolving committee settings")

        committee_raw = group_settings.get("committee", {}) if isinstance(group_settings, dict) else {}
        if not isinstance(committee_raw, dict):
            committee_raw = {}
        policy_raw = committee_raw.get("policy", {})
        if not isinstance(policy_raw, dict):
            policy_raw = {}
        actions_raw = committee_raw.get("actions", {})
        if not isinstance(actions_raw, dict):
            actions_raw = {}
        prompting_raw = committee_raw.get("prompting", {})
        if not isinstance(prompting_raw, dict):
            prompting_raw = {}

        fallback_notes: List[str] = []

        configured_supervisor_id = committee_raw.get("supervisor_id")
        if isinstance(configured_supervisor_id, str):
            configured_supervisor_id = configured_supervisor_id.strip()
        else:
            configured_supervisor_id = ""
        supervisor_id = configured_supervisor_id if configured_supervisor_id in group_assistants else group_assistants[0]
        if configured_supervisor_id and configured_supervisor_id != supervisor_id:
            fallback_notes.append("supervisor_not_in_participants")

        supervisor_obj = assistant_config_map.get(supervisor_id)
        default_raw_limit = getattr(supervisor_obj, "max_rounds", None) if supervisor_obj else None
        raw_limit = cls._coerce_int(policy_raw.get("max_rounds"))
        if raw_limit is None and "max_rounds" in policy_raw:
            fallback_notes.append("invalid_max_rounds")
        if raw_limit is None:
            raw_limit = default_raw_limit
        round_policy_fn = resolve_round_policy or CommitteePolicy.resolve_committee_round_policy
        base_policy = round_policy_fn(raw_limit, participant_count=len(group_assistants))

        min_member_turns = cls._coerce_int(policy_raw.get("min_member_turns_before_finish"))
        if min_member_turns is None and "min_member_turns_before_finish" in policy_raw:
            fallback_notes.append("invalid_min_member_turns_before_finish")
        if min_member_turns is None:
            min_member_turns = int(base_policy["min_member_turns_before_finish"])
        min_member_turns = max(1, min(min_member_turns, 6))

        min_total_rounds = cls._coerce_int(policy_raw.get("min_total_rounds_before_finish"))
        if min_total_rounds is None and "min_total_rounds_before_finish" in policy_raw:
            fallback_notes.append("invalid_min_total_rounds_before_finish")
        if min_total_rounds is None:
            min_total_rounds = int(base_policy["min_total_rounds_before_finish"])
        min_total_rounds = max(0, min_total_rounds)

        max_rounds = CommitteePolicy.resolve_group_round_limit(
            raw_limit,
            fallback=max(int(base_policy["max_rounds"]), min_total_rounds),
            hard_cap=cls._MAX_ROUNDS_HARD_CAP,
        )
        max_rounds = max(max_rounds, min_total_rounds)

        max_parallel_speakers = cls._coerce_int(policy_raw.get("max_parallel_speakers"))
        if max_parallel_speakers is None and "max_parallel_speakers" in policy_raw:
            fallback_notes.append("invalid_max_parallel_speakers")
        if max_parallel_speakers is None:
            max_parallel_speakers = 3
        max_parallel_speakers = max(1, min(max_parallel_speakers, cls._MAX_PARALLEL_SPEAKERS_CAP))

        role_retry_limit = cls._coerce_int(policy_raw.get("role_retry_limit"))
        if role_retry_limit is None and "role_retry_limit" in policy_raw:
            fallback_notes.append("invalid_role_retry_limit")
        if role_retry_limit is None:
            role_retry_limit = 1
        role_retry_limit = max(0, min(role_retry_limit, cls._ROLE_RETRY_LIMIT_CAP))

        allow_parallel_speak = actions_raw.get("allow_parallel_speak", True)
        if not isinstance(allow_parallel_speak, bool):
            allow_parallel_speak = True
            fallback_notes.append("invalid_allow_parallel_speak")
        allow_finish = actions_raw.get("allow_finish", True)
        if not isinstance(allow_finish, bool):
            allow_finish = True
            fallback_notes.append("invalid_allow_finish")

        supervisor_prompt_template = prompting_raw.get("supervisor_system_prompt_template")
        if not isinstance(supervisor_prompt_template, str) or not supervisor_prompt_template.strip():
            supervisor_prompt_template = None

        summary_prompt_template = prompting_raw.get("summary_instruction_template")
        if not isinstance(summary_prompt_template, str) or not summary_prompt_template.strip():
            summary_prompt_template = None

        return ResolvedCommitteeSettings(
            supervisor_id=supervisor_id,
            max_rounds=max_rounds,
            min_member_turns_before_finish=min_member_turns,
            min_total_rounds_before_finish=min_total_rounds,
            max_parallel_speakers=max_parallel_speakers,
            role_retry_limit=role_retry_limit,
            allow_parallel_speak=allow_parallel_speak,
            allow_finish=allow_finish,
            supervisor_system_prompt_template=supervisor_prompt_template,
            summary_instruction_template=summary_prompt_template,
            fallback_notes=fallback_notes,
        )

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        if value is None or value is True or value is False:
            return None
        try:
            return int(value)
        except Exception:
            return None
