# DeepSeek LLM Logging - Complete Implementation

## Summary

I've implemented comprehensive logging for all DeepSeek LLM interactions. Now you can see **exactly** what you send to DeepSeek and what you receive back.

## What Changed

### 1. New Logger Module
**File**: `src/utils/llm_logger.py`
- Logs every LLM interaction with full details
- Saves to daily log files in `logs/` directory
- Captures timestamps, session IDs, messages sent, and responses received

### 2. Agent Integration
**File**: `src/agents/simple_agent.py`
- Added logging to the `chat_node` function
- Every DeepSeek API call is now logged
- Includes error logging if calls fail

### 3. State Updates
**File**: `src/state/agent_state.py`
- Added `session_id` field to track which conversation
- Allows correlating logs with specific sessions

**File**: `src/api/services/agent_service.py`
- Passes session_id to agent for logging

**File**: `src/main.py`
- CLI mode now generates session IDs
- All CLI interactions are also logged

## How to Use

### 1. Start Using (No Setup Required)

The logging is automatic! Just use your system normally:

**Web Interface**:
```bash
# Terminal 1: Start backend
venv\Scripts\activate
uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Start frontend
cd frontend
npm run dev
```

**CLI Mode**:
```bash
venv\Scripts\activate
python -m src.main
```

### 2. View Logs

**See all interactions for today**:
```bash
python view_llm_logs.py
```

Example output:
```
🔄 INTERACTION #1
⏰ Timestamp: 2026-01-25T14:30:22.123456
🆔 Session: 550e8400-e29b4...
🤖 Model: deepseek-chat

📤 SENT TO DEEPSEEK (2 messages):
────────────────────────────────────────
👤 Message 1 (HumanMessage):
   Hello

🤖 Message 2 (AIMessage):
   Hi! How can I help you?

📥 RECEIVED FROM DEEPSEEK:
────────────────────────────────────────
🤖 Response (AIMessage):
   I'm here to assist you with any questions!
```

**View a specific interaction in full detail**:
```bash
python view_llm_logs.py -i 2
```

This shows the complete JSON with full message contents.

**View older logs**:
```bash
python view_llm_logs.py -f logs/llm_interactions_20260124.log
```

### 3. Debug Duplicate Messages

If DeepSeek says you sent duplicate "hello" messages:

1. Run: `python view_llm_logs.py`
2. Find the interaction number
3. Run: `python view_llm_logs.py -i <number>`
4. Look at `request.messages` array - you'll see EXACTLY what was sent

## Log Format

Each interaction is logged as structured JSON:

```json
{
  "timestamp": "2026-01-25T14:30:22.123456",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "deepseek-chat",
  "request": {
    "message_count": 3,
    "messages": [
      {"type": "HumanMessage", "content": "Hello", "role": "user"},
      {"type": "AIMessage", "content": "Hi!", "role": "assistant"},
      {"type": "HumanMessage", "content": "How are you?", "role": "user"}
    ]
  },
  "response": {
    "type": "AIMessage",
    "content": "I'm doing well, thanks!",
    "role": "assistant"
  }
}
```

## Log File Locations

```
logs/
├── llm_interactions_20260125.log  ← Today's log
├── llm_interactions_20260124.log  ← Yesterday's log
└── llm_interactions_20260123.log  ← Older logs
```

## Console Output

While running, you'll also see real-time summaries:

```
[INFO] Sending 2 messages to DeepSeek for session 550e8400...
[INFO] LLM Call | Session: 550e8400... | Sent: 2 msgs | Received: 157 chars
```

## Files Modified

1. ✅ `src/utils/llm_logger.py` - Logger implementation (NEW)
2. ✅ `src/agents/simple_agent.py` - Integrated logging
3. ✅ `src/state/agent_state.py` - Added session_id field
4. ✅ `src/api/services/agent_service.py` - Pass session_id to agent
5. ✅ `src/main.py` - CLI logging support
6. ✅ `view_llm_logs.py` - Log viewer tool (NEW)
7. ✅ `docs/LLM_LOGGING.md` - Full documentation (NEW)

## Next Steps

1. **Test it**: Send a message through the web interface or CLI
2. **View logs**: Run `python view_llm_logs.py`
3. **Check the logs directory**: Look for `logs/llm_interactions_*.log` files

Now you have complete visibility into every DeepSeek interaction!
