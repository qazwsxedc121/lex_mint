"""Unit tests for MemoryConfigService."""

from pathlib import Path

from src.api.services.memory_config_service import MemoryConfigService


def test_memory_config_service_creates_default_file(temp_config_dir):
    config_path = temp_config_dir / "memory_config.yaml"

    service = MemoryConfigService(config_path=str(config_path))

    assert config_path.exists()
    flat = service.get_flat_config()
    assert flat["enabled"] is False
    assert flat["profile_id"] == "local-default"
    assert flat["collection_name"] == "memory_main"
    assert "fact" in flat["enabled_layers"]
    assert "instruction" in flat["enabled_layers"]


def test_memory_config_service_updates_flat_values(temp_config_dir):
    config_path = temp_config_dir / "memory_config.yaml"
    service = MemoryConfigService(config_path=str(config_path))

    service.save_flat_config(
        {
            "enabled": True,
            "top_k": 5,
            "score_threshold": 0.5,
            "global_enabled": True,
            "assistant_enabled": False,
            "enabled_layers": ["fact"],
        }
    )

    reloaded = MemoryConfigService(config_path=str(config_path))
    flat = reloaded.get_flat_config()

    assert flat["top_k"] == 5
    assert flat["score_threshold"] == 0.5
    assert flat["assistant_enabled"] is False
    assert flat["enabled_layers"] == ["fact"]


def test_memory_config_service_persists_extraction_rules(temp_config_dir):
    config_path = temp_config_dir / "memory_config.yaml"
    service = MemoryConfigService(config_path=str(config_path))

    service.save_config(
        {
            "extraction": {
                "instruction_markers": ["talk like a pirate"],
                "fact_markers": ["favorite editor is "],
                "instruction_confidence": 0.97,
                "instruction_importance": 0.88,
                "fact_confidence": 0.73,
                "fact_importance": 0.54,
            }
        }
    )

    reloaded = MemoryConfigService(config_path=str(config_path))
    extraction = reloaded.config.extraction

    assert extraction.instruction_markers == ["talk like a pirate"]
    assert extraction.fact_markers == ["favorite editor is "]
    assert extraction.instruction_confidence == 0.97
    assert extraction.instruction_importance == 0.88
    assert extraction.fact_confidence == 0.73
    assert extraction.fact_importance == 0.54
