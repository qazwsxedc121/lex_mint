"""
Test script for Title Generation feature

This script tests the title generation functionality end-to-end.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.api.services.conversation_storage import ConversationStorage
from src.api.services.title_generation_service import TitleGenerationService


async def test_title_generation():
    """Test title generation service"""
    print("=" * 60)
    print("Title Generation Feature Test")
    print("=" * 60)

    # Initialize services
    storage = ConversationStorage(conversations_dir="conversations")
    title_service = TitleGenerationService(storage=storage)

    # Load config
    print("\n[Step 1] Loading configuration...")
    config = title_service.config
    print(f"  - Enabled: {config.enabled}")
    print(f"  - Trigger Threshold: {config.trigger_threshold}")
    print(f"  - Model ID: {config.model_id}")
    print(f"  - Max Context Rounds: {config.max_context_rounds}")
    print(f"  - Timeout: {config.timeout_seconds}s")
    print("[OK] Configuration loaded successfully")

    # Test should_generate_title logic
    print("\n[Step 2] Testing trigger logic...")

    # Test case 1: Default title, threshold met
    should_gen = title_service.should_generate_title(2, "New Conversation")
    print(f"  - Default title, 2 messages (1 round): {should_gen}")
    assert should_gen == True, "Should generate for default title"

    # Test case 2: Truncated title
    should_gen = title_service.should_generate_title(2, "This is a very long title...")
    print(f"  - Truncated title, 2 messages: {should_gen}")
    assert should_gen == True, "Should generate for truncated title"

    # Test case 3: Already has good title
    should_gen = title_service.should_generate_title(2, "Good Title")
    print(f"  - Good title, 2 messages: {should_gen}")
    assert should_gen == False, "Should not regenerate good title"

    # Test case 4: Below threshold
    should_gen = title_service.should_generate_title(0, "New Conversation")
    print(f"  - Default title, 0 messages: {should_gen}")
    assert should_gen == False, "Should not generate below threshold"

    print("[OK] Trigger logic working correctly")

    # Test config save/reload
    print("\n[Step 3] Testing config save/reload...")
    original_threshold = config.trigger_threshold
    try:
        title_service.save_config({'trigger_threshold': 2})
        assert title_service.config.trigger_threshold == 2, "Config not updated"
        print(f"  - Saved new threshold: 2")

        # Reload
        title_service.reload_config()
        assert title_service.config.trigger_threshold == 2, "Config not persisted"
        print(f"  - Reloaded config: threshold = {title_service.config.trigger_threshold}")

        # Restore original
        title_service.save_config({'trigger_threshold': original_threshold})
        print(f"  - Restored original threshold: {original_threshold}")
        print("[OK] Config save/reload working")
    except Exception as e:
        print(f"[ERROR] Config save/reload failed: {e}")
        raise

    print("\n" + "=" * 60)
    print("All tests passed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start backend: ./venv/Scripts/uvicorn src.api.main:app --reload --port <API_PORT>")
    print("2. Start frontend: cd frontend && npm run dev")
    print("3. Navigate to Settings > Title Generation")
    print("4. Send a message and watch the title auto-generate")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_title_generation())
