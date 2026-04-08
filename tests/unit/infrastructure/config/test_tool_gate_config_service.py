"""Tests for regex tool-gate config service."""

from __future__ import annotations

from src.infrastructure.config.tool_gate_config_service import ToolGateConfigService


def test_tool_gate_config_service_creates_and_normalizes(tmp_path):
    config_path = tmp_path / "tool_gate_config.yaml"
    service = ToolGateConfigService(config_path=str(config_path))

    assert config_path.exists()
    assert service.config.enabled is False
    assert service.config.rules == []

    config_path.write_text(
        """
tool_gate:
  enabled: true
  rules:
    - id: stop_code_tools
      enabled: true
      priority: "9"
      pattern: "(?i)常识|定义|是什么"
      flags: "ix"
      include_tools: ["web_search", "web_search", "", null]
      exclude_tools: ["execute_python", "execute_javascript"]
    - id: bad_rule
      enabled: true
      priority: "oops"
      pattern: ""
""".strip(),
        encoding="utf-8",
    )
    service.reload_config()

    assert service.config.enabled is True
    assert len(service.config.rules) == 1
    rule = service.config.rules[0]
    assert rule.id == "stop_code_tools"
    assert rule.priority == 9
    assert rule.flags == "i"
    assert rule.include_tools == ["web_search"]
    assert rule.exclude_tools == ["execute_python", "execute_javascript"]


def test_tool_gate_config_service_falls_back_on_bad_yaml(tmp_path):
    config_path = tmp_path / "tool_gate_config.yaml"
    config_path.write_text("tool_gate: [", encoding="utf-8")

    service = ToolGateConfigService(config_path=str(config_path))
    assert service.config.enabled is False
