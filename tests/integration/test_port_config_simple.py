"""
Simple port configuration test.

Tests that API_PORT configuration actually works, without starting a real server.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def test_config_default_port():
    """Test default port is 8888."""
    print("[TEST 1] Testing default port from config.py...")

    # Clean environment
    if 'API_PORT' in os.environ:
        del os.environ['API_PORT']

    os.environ['DEEPSEEK_API_KEY'] = 'test_key'

    from src.api.config import Settings
    settings = Settings()

    assert settings.api_port == 8888, f"Expected 8888, got {settings.api_port}"
    print(f"[OK] Default port is 8888")

    del os.environ['DEEPSEEK_API_KEY']


def test_config_env_override():
    """Test that API_PORT env var overrides default."""
    print("\n[TEST 2] Testing API_PORT environment variable override...")

    test_port = 9999
    os.environ['API_PORT'] = str(test_port)
    os.environ['DEEPSEEK_API_KEY'] = 'test_key'

    from src.api.config import Settings
    # Force reload
    import importlib
    import src.api.config as config_module
    importlib.reload(config_module)

    settings = config_module.Settings()

    assert settings.api_port == test_port, f"Expected {test_port}, got {settings.api_port}"
    print(f"[OK] API_PORT={test_port} correctly overrides default")

    del os.environ['API_PORT']
    del os.environ['DEEPSEEK_API_KEY']


def test_dotenv_loading():
    """Test that .env file is loaded correctly."""
    print("\n[TEST 3] Testing .env file loading...")

    env_file = project_root / ".env"
    if not env_file.exists():
        print("[SKIP] .env file not found")
        return

    # Read API_PORT from .env
    with open(env_file) as f:
        for line in f:
            if line.startswith('API_PORT='):
                port_from_file = line.split('=')[1].strip()
                print(f"[INFO] Found API_PORT={port_from_file} in .env")

                # Verify it matches config
                from dotenv import load_dotenv
                load_dotenv()

                port_from_env = os.environ.get('API_PORT', '8888')
                assert port_from_env == port_from_file, \
                    f"Mismatch: .env has {port_from_file}, env has {port_from_env}"
                print(f"[OK] .env file loaded correctly")
                return

    print("[SKIP] No API_PORT in .env file")


if __name__ == "__main__":
    print("=" * 80)
    print("PORT CONFIGURATION TEST (Simple Version)")
    print("=" * 80)

    try:
        test_config_default_port()
        test_config_env_override()
        test_dotenv_loading()

        print("\n" + "=" * 80)
        print("ALL TESTS PASSED!")
        print("=" * 80)
        print("\nConclusion:")
        print("- Config default port: 8888")
        print("- Environment variable override: WORKS")
        print("- .env file loading: WORKS")
        print("\nYou can change the port by editing API_PORT in .env file")

    except AssertionError as e:
        print(f"\n[FAIL] {e}")
        sys.exit(1)
