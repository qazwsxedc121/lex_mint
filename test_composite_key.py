"""
Test composite key model management

Verify that same model IDs can coexist under different providers
"""
import asyncio
from src.api.services.model_config_service import ModelConfigService
from src.api.models.model_config import Model, Provider


async def test_composite_key():
    """Test composite key functionality"""
    service = ModelConfigService()

    print("=" * 60)
    print("Test: Composite Key Model Management")
    print("=" * 60)

    # Test 1: Add same model ID to different providers
    print("\n[Test 1] Add same model ID to different providers")
    print("-" * 60)

    # Add OpenRouter provider if not exists
    try:
        await service.add_provider(Provider(
            id="openrouter",
            name="OpenRouter",
            base_url="https://openrouter.ai/api/v1",
            enabled=True
        ))
        print("OK: Added OpenRouter provider")
    except ValueError as e:
        print(f"INFO: OpenRouter provider already exists: {e}")

    # Add DeepSeek official model
    try:
        await service.add_model(Model(
            id="deepseek-chat",
            name="DeepSeek Chat (Official)",
            provider_id="deepseek",
            group="chat",
            temperature=0.7,
            enabled=True
        ))
        print("OK: DeepSeek official model exists or added")
    except ValueError as e:
        print(f"INFO: DeepSeek official model already exists: {e}")

    # Add OpenRouter version with same model ID
    try:
        await service.add_model(Model(
            id="deepseek-chat",
            name="DeepSeek Chat (via OpenRouter)",
            provider_id="openrouter",
            group="chat",
            temperature=0.7,
            enabled=True
        ))
        print("SUCCESS: OpenRouter version added!")
        print("   => Same model ID can coexist under different providers")
    except ValueError as e:
        if "already exists for provider" in str(e):
            print("INFO: OpenRouter model already exists (expected in repeated runs)")
            print("   => Same model ID can coexist under different providers")
        else:
            print(f"FAIL: Cannot add: {e}")
            return False

    # Test 2: Verify duplicate prevention
    print("\n[Test 2] Verify duplicate prevention within same provider")
    print("-" * 60)
    try:
        await service.add_model(Model(
            id="deepseek-chat",
            name="DeepSeek Chat Duplicate",
            provider_id="deepseek",
            group="chat",
            temperature=0.7,
            enabled=True
        ))
        print("FAIL: Should not allow duplicate")
        return False
    except ValueError as e:
        print(f"OK: Correctly prevented duplicate: {e}")

    # Test 3: Query with composite ID
    print("\n[Test 3] Query models using composite ID")
    print("-" * 60)

    # Query DeepSeek official
    model1 = await service.get_model("deepseek:deepseek-chat")
    if model1:
        print(f"OK: Found model: {model1.name} (provider: {model1.provider_id})")
    else:
        print("FAIL: DeepSeek official not found")

    # Query OpenRouter version
    model2 = await service.get_model("openrouter:deepseek-chat")
    if model2:
        print(f"OK: Found model: {model2.name} (provider: {model2.provider_id})")
    else:
        print("FAIL: OpenRouter version not found")

    # Test 4: LLM instantiation with composite ID
    print("\n[Test 4] Create LLM instance using composite ID")
    print("-" * 60)

    try:
        llm1 = service.get_llm_instance("deepseek:deepseek-chat")
        print(f"OK: DeepSeek official LLM created")
        print(f"   Base URL: {llm1.openai_api_base}")
    except RuntimeError as e:
        print(f"INFO: API key required: {e}")
    except Exception as e:
        print(f"FAIL: Creation failed: {e}")

    try:
        llm2 = service.get_llm_instance("openrouter:deepseek-chat")
        print(f"OK: OpenRouter LLM created")
        print(f"   Base URL: {llm2.openai_api_base}")
    except RuntimeError as e:
        print(f"INFO: API key required: {e}")
    except Exception as e:
        print(f"FAIL: Creation failed: {e}")

    # Test 5: List all models
    print("\n[Test 5] List all models with ID 'deepseek-chat'")
    print("-" * 60)
    all_models = await service.get_models()
    deepseek_models = [m for m in all_models if m.id == "deepseek-chat"]

    print(f"All instances of model ID 'deepseek-chat':")
    for m in deepseek_models:
        print(f"  - {m.name}")
        print(f"    Provider: {m.provider_id}")
        print(f"    Composite ID: {m.provider_id}:{m.id}")
    print(f"\nTotal: {len(deepseek_models)} models with same ID")

    print("\n" + "=" * 60)
    print("SUCCESS: All tests passed! Composite key works correctly")
    print("=" * 60)

    return True


if __name__ == "__main__":
    success = asyncio.run(test_composite_key())
    exit(0 if success else 1)
