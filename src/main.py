"""Main entry point for the agent system."""

from dotenv import load_dotenv
import uuid

load_dotenv()

from src.agents.simple_llm import call_llm

def main():
    """Run the simple agent example."""
    # Generate session ID for this CLI session
    session_id = str(uuid.uuid4())

    print("Starting LangGraph Agent...")
    print(f"Session ID: {session_id}")
    print("Type your message (or 'quit' to exit):")

    messages = []

    while True:
        user_input = input("\nUser: ")
        if user_input.lower() in ['quit', 'exit']:
            break

        # 添加用户消息
        messages.append({"role": "user", "content": user_input})

        # 调用 LLM（只调用一次）
        response = call_llm(messages, session_id=session_id)

        # 添加助手回复到历史
        messages.append({"role": "assistant", "content": response})

        print(f"Agent: {response}")


if __name__ == "__main__":
    main()
