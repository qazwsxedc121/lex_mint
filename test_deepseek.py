"""Simple script to verify DeepSeek API connection."""

import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    print("Error: DEEPSEEK_API_KEY not found in environment variables")
    print("Please create a .env file with your DeepSeek API key")
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
