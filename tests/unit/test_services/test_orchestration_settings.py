"""Unit tests for group-orchestration settings resolver."""

from types import SimpleNamespace

from src.api.services.orchestration.settings import GroupSettingsResolver


def _assistant(max_rounds: int = 6):
    return SimpleNamespace(max_rounds=max_rounds)


def test_normalize_group_settings_strips_invalid_fields():
    raw = {
        "committee": {
            "supervisor_id": " sup ",
            "policy": {
                "max_rounds": "8",
                "min_member_turns_before_finish": "bad",
                "role_retry_limit": 2,
            },
            "actions": {
                "allow_parallel_speak": False,
                "allow_finish": "oops",
            },
            "prompting": {
                "supervisor_system_prompt_template": "   custom prompt  ",
                "summary_instruction_template": "",
            },
        }
    }

    normalized = GroupSettingsResolver.normalize_group_settings(raw)
    assert normalized["version"] == 1
    assert normalized["committee"]["supervisor_id"] == "sup"
    assert normalized["committee"]["policy"]["max_rounds"] == 8
    assert "min_member_turns_before_finish" not in normalized["committee"]["policy"]
    assert normalized["committee"]["policy"]["role_retry_limit"] == 2
    assert normalized["committee"]["actions"]["allow_parallel_speak"] is False
    assert "allow_finish" not in normalized["committee"]["actions"]
    assert (
        normalized["committee"]["prompting"]["supervisor_system_prompt_template"]
        == "custom prompt"
    )
    assert "summary_instruction_template" not in normalized["committee"]["prompting"]


def test_resolve_committee_settings_prefers_explicit_supervisor():
    resolved = GroupSettingsResolver.resolve(
        group_mode="committee",
        group_assistants=["a1", "a2", "a3"],
        group_settings={
            "committee": {
                "supervisor_id": "a2",
                "policy": {
                    "max_rounds": 9,
                    "max_parallel_speakers": 4,
                    "role_retry_limit": 2,
                },
            }
        },
        assistant_config_map={
            "a1": _assistant(max_rounds=3),
            "a2": _assistant(max_rounds=3),
            "a3": _assistant(max_rounds=3),
        },
    )

    assert resolved.committee is not None
    assert resolved.committee.supervisor_id == "a2"
    assert resolved.committee.max_rounds == 9
    assert resolved.committee.max_parallel_speakers == 4
    assert resolved.committee.role_retry_limit == 2


def test_resolve_committee_settings_fallbacks_and_notes():
    resolved = GroupSettingsResolver.resolve(
        group_mode="committee",
        group_assistants=["a1", "a2"],
        group_settings={
            "committee": {
                "supervisor_id": "ghost",
                "policy": {
                    "max_rounds": "bad",
                    "role_retry_limit": "oops",
                },
                "actions": {
                    "allow_finish": "maybe",
                },
            }
        },
        assistant_config_map={"a1": _assistant(max_rounds=5), "a2": _assistant(max_rounds=5)},
    )

    assert resolved.committee is not None
    assert resolved.committee.supervisor_id == "a1"
    assert resolved.committee.max_rounds == 5
    assert resolved.committee.role_retry_limit == 1
    assert resolved.committee.allow_finish is True
    assert "supervisor_not_in_participants" in resolved.committee.fallback_notes


def test_resolve_round_robin_mode_has_no_committee_payload():
    resolved = GroupSettingsResolver.resolve(
        group_mode="round_robin",
        group_assistants=["a1", "a2"],
        group_settings={"committee": {"supervisor_id": "a2"}},
        assistant_config_map={"a1": _assistant(), "a2": _assistant()},
    )

    assert resolved.group_mode == "round_robin"
    assert resolved.committee is None

