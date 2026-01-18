# LangGraph Agent Example

Basic LangGraph implementation demonstrating:
- State management with TypedDict
- Agent nodes and conditional edges
- Simple chat interface

## Installation

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install langgraph langchain-openai python-dotenv
```

## Configuration

Create a `.env` file in the project root:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

## Running

```bash
# Run the agent
python -m src.main
```

## Project Structure

```
src/
├── agents/
│   ├── __init__.py
│   └── simple_agent.py    # Main agent implementation
├── state/
│   ├── __init__.py
│   └── agent_state.py     # State definitions
├── utils/
│   └── __init__.py
├── __init__.py
└── main.py                # Entry point
tests/
└── unit/
    ├── __init__.py
    └── test_simple_agent.py  # Unit tests
```

## Testing

```bash
# Run all tests
pytest

# Run single test
pytest tests/unit/test_simple_agent.py

# Run with coverage
pytest --cov=src --cov-report=html
```

## Code Quality

```bash
# Linting
ruff check .

# Format code
ruff format .

# Type checking
mypy .
```
