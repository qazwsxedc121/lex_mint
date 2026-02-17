"""Simple script to verify DeepSeek API connection."""

from pathlib import Path
from langchain_openai import ChatOpenAI
import yaml


def load_deepseek_key() -> str | None:
    path = Path.home() / ".lex_mint" / "keys_config.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    return data.get("providers", {}).get("deepseek", {}).get("api_key")

api_key = load_deepseek_key()
if not api_key:
    print("Error: DeepSeek API key not found")
    print("Please set key in ~/.lex_mint/keys_config.yaml")
    exit(1)

print("Testing DeepSeek API connection...")

try:
    llm = ChatOpenAI(
        model="deepseek-chat",
        temperature=0.7,
        base_url="https://api.deepseek.com",
        api_key=api_key
    )
    
    response = llm.invoke("Hello! Can you hear me? Please respond with 'Yes, I can hear you!'")
    
    print(f"\nDeepSeek Response: {response.content}")
    print("\nAPI connection successful!")
    
except Exception as e:
    print(f"\nError connecting to DeepSeek API: {e}")
    exit(1)
