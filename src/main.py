"""Main entry point for the agent system."""

from src.agents.simple_agent import create_simple_agent

def main():
    """Run the simple agent example."""
    agent = create_simple_agent()
    
    print("Starting LangGraph Agent...")
    print("Type your message (or 'quit' to exit):")
    
    state = {"messages": []}
    
    while True:
        user_input = input("\nUser: ")
        if user_input.lower() in ['quit', 'exit']:
            break
        
        state["messages"].append({"role": "user", "content": user_input})
        
        result = agent.invoke(state)
        state = result
        
        last_message = result["messages"][-1]
        print(f"Agent: {last_message.get('content', '')}")


if __name__ == "__main__":
    main()
