# LLM Interaction Logging

Comprehensive logging system to track all DeepSeek API interactions for debugging and auditing.

## What Gets Logged

Every interaction with DeepSeek LLM is logged with:

1. **Timestamp** - Exact time of the interaction
2. **Session ID** - Which conversation session
3. **Messages Sent** - All messages sent to DeepSeek (full conversation history)
   - Message type (HumanMessage/AIMessage)
   - Full content of each message
4. **Response Received** - Complete response from DeepSeek
   - Response type
   - Full content
5. **Errors** - Any errors that occur during LLM calls

## Log File Location

Logs are stored in the `logs/` directory with daily rotation:
```
logs/llm_interactions_YYYYMMDD.log
```

Example: `logs/llm_interactions_20260125.log`

## Viewing Logs

### Quick Summary View

View all interactions for today:
```bash
python view_llm_logs.py
```

This shows a summary with:
- Interaction number
- Timestamp
- Session ID
- Number of messages sent
- Preview of each message (first 200 chars)
- Preview of response (first 200 chars)

### View Specific Log File

View a specific date's logs:
```bash
python view_llm_logs.py -f logs/llm_interactions_20260124.log
```

### View Full Interaction Details

See complete JSON for a specific interaction:
```bash
python view_llm_logs.py -i 3
```

This shows interaction #3 in full detail with complete message contents.

### View Specific Interaction from Specific File

```bash
python view_llm_logs.py -f logs/llm_interactions_20260124.log -i 2
```

## Log Format

Each log entry is formatted as JSON:

```json
{
  "timestamp": "2026-01-25T14:30:22.123456",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "deepseek-chat",
  "request": {
    "message_count": 2,
    "messages": [
      {
        "type": "HumanMessage",
        "content": "Hello",
        "role": "user"
      },
      {
        "type": "AIMessage",
        "content": "Hi! How can I help?",
        "role": "assistant"
      }
    ]
  },
  "response": {
    "type": "AIMessage",
    "content": "I'm here to assist you!",
    "role": "assistant"
  }
}
```

## Console Output

When the API is running, you'll also see real-time summaries in the console:

```
[INFO] LLM Call | Session: 550e8400... | Sent: 2 msgs | Received: 157 chars
```

## Use Cases

### Check for Duplicate Messages

If DeepSeek says you sent duplicate messages, check the log:

```bash
python view_llm_logs.py -i 1
```

Look at the `request.messages` array to see exactly what was sent.

### Debug Conversation Context

See what conversation history is being sent:

```bash
python view_llm_logs.py
```

Check if the full conversation is being included or if messages are missing.

### Investigate Response Issues

If responses seem odd, view the full interaction:

```bash
python view_llm_logs.py -i <interaction_number>
```

Compare what you sent vs. what you received.

### Track API Usage

Count total interactions per day by viewing the log summary.

## Implementation Details

- **Location**: `src/utils/llm_logger.py`
- **Integration**: `src/agents/simple_agent.py` (chat_node function)
- **State Tracking**: Session ID passed through agent state
- **Error Handling**: Errors are logged before re-raising

## Disabling Logs

To disable or reduce logging, modify the log level in `src/utils/llm_logger.py`:

```python
# Change from DEBUG to INFO to reduce verbosity
self.logger.setLevel(logging.INFO)
```

Or remove the file handler to disable file logging entirely.
