# Title Generation Feature - Implementation Complete

## Overview

Automatic conversation title generation using a small LLM model. Titles are generated in the background after the first conversation round, replacing the simple 30-character truncation mechanism.

## Features

- **Automatic Generation**: Triggers after configurable number of conversation rounds (default: 1)
- **Background Processing**: Runs asynchronously without blocking the main chat flow
- **Manual Trigger**: Button to regenerate title on demand
- **Configurable**: Full control via settings UI
- **Cost-Effective**: Uses small models (e.g., GPT-4o-mini) and only generates once per conversation

## Implementation Summary

### Backend Files

**New Files:**
1. `config/title_generation_config.yaml` - Configuration file
2. `src/api/services/title_generation_service.py` - Core service (209 lines)
3. `src/api/routers/title_generation.py` - API endpoints (123 lines)

**Modified Files:**
4. `src/api/services/conversation_storage.py` - Added `update_session_metadata()` method
5. `src/api/services/agent_service_simple.py` - Integrated title generation trigger
6. `src/api/main.py` - Registered title generation router

### Frontend Files

**New Files:**
7. `frontend/src/modules/settings/TitleGenerationSettings.tsx` - Settings page (300+ lines)

**Modified Files:**
8. `frontend/src/services/api.ts` - Added API functions
9. `frontend/src/modules/settings/SettingsSidebar.tsx` - Added navigation item
10. `frontend/src/App.tsx` - Registered route
11. `frontend/src/modules/chat/ChatView.tsx` - Added regenerate button + auto-refresh

## How It Works

### Automatic Generation Flow

1. User sends a message
2. AI responds and message is saved
3. System checks if title generation should trigger:
   - Is feature enabled?
   - Is title still default/truncated?
   - Has threshold been reached?
4. If yes, creates background task to generate title
5. Title generation service:
   - Loads recent conversation (configurable rounds)
   - Calls small model with prompt template
   - Updates session metadata with new title
6. Frontend auto-refreshes after 1 second to show new title

### Manual Generation

1. User clicks "Regenerate Title" button in chat header
2. Frontend calls `/api/title-generation/generate` endpoint
3. Backend generates title synchronously and returns result
4. Frontend refreshes session list to show new title

## Configuration

### File: `config/title_generation_config.yaml`

```yaml
title_generation:
  enabled: true                                    # Enable/disable feature
  trigger_threshold: 1                             # Conversation rounds before triggering
  model_id: "openrouter:openai/gpt-4o-mini"       # Model for title generation
  max_context_rounds: 3                            # Max conversation rounds to use as context
  timeout_seconds: 10                              # Timeout for model call
  prompt_template: |                               # Prompt sent to model
    Please generate a concise title (10-30 characters) based on the
    following conversation.
    Return only the title text, without quotes or formatting.

    Conversation:
    {conversation_text}
```

### UI Configuration

Navigate to **Settings > Title Generation** to configure via web interface.

## API Endpoints

### GET /api/title-generation/config
Get current configuration.

**Response:**
```json
{
  "enabled": true,
  "trigger_threshold": 1,
  "model_id": "openrouter:openai/gpt-4o-mini",
  "prompt_template": "...",
  "max_context_rounds": 3,
  "timeout_seconds": 10
}
```

### PUT /api/title-generation/config
Update configuration (partial updates supported).

**Request:**
```json
{
  "enabled": true,
  "trigger_threshold": 2
}
```

### POST /api/title-generation/generate
Manually generate title for a session.

**Request:**
```json
{
  "session_id": "uuid-here"
}
```

**Response:**
```json
{
  "message": "Title generated successfully",
  "title": "Generated Title"
}
```

## Testing

Run the test script:
```bash
./venv/Scripts/python test_title_generation.py
```

Expected output:
```
============================================================
Title Generation Feature Test
============================================================

[Step 1] Loading configuration...
  - Enabled: True
  - Trigger Threshold: 1
  - Model ID: openrouter:openai/gpt-4o-mini
  ...
[OK] Configuration loaded successfully

[Step 2] Testing trigger logic...
  - Default title, 2 messages (1 round): True
  - Truncated title, 2 messages: True
  - Good title, 2 messages: False
  - Default title, 0 messages: False
[OK] Trigger logic working correctly

[Step 3] Testing config save/reload...
[OK] Config save/reload working

============================================================
All tests passed!
============================================================
```

## Usage

### 1. Start the Application

**Backend:**
```bash
./venv/Scripts/uvicorn src.api.main:app --reload --port 8888
```

**Frontend:**
```bash
cd frontend
npm run dev
```

### 2. Configure the Feature

1. Navigate to **Settings > Title Generation**
2. Ensure "Enable automatic title generation" is checked
3. Select a small model (e.g., GPT-4o-mini)
4. Adjust trigger threshold (default: 1 round)
5. Customize prompt template if needed
6. Click "Save Settings"

### 3. Test Automatic Generation

1. Create a new conversation
2. Send a message
3. Wait for AI response
4. After ~1 second, the title should automatically update from "New Conversation" to an AI-generated title

### 4. Manual Regeneration

1. In any conversation, click the "Regenerate Title" button in the header
2. Title will be regenerated based on current conversation content

## Error Handling

- **Timeout Protection**: 10-second timeout prevents hanging
- **Graceful Degradation**: If generation fails, original title is kept
- **No User Impact**: All errors are logged but don't affect chat functionality
- **Background Execution**: Title generation never blocks message sending

## Logs

Title generation events are logged in `logs/server.log`:

```
[TitleGen] Starting title generation for session {session_id}
[TitleGen] Calling model openrouter:openai/gpt-4o-mini
[TitleGen] Generated title: Example Title
[TitleGen] Title updated successfully for session {session_id}
```

## Cost Considerations

- **Per-Conversation**: Title generated only once per conversation (when threshold is reached)
- **Small Models**: Recommended to use cheap models like GPT-4o-mini
- **Token Usage**: Typically 200-500 tokens per generation (~$0.0001-0.0005)
- **Monitoring**: Check logs for usage statistics

## Troubleshooting

### Title Not Generating

1. Check if feature is enabled in settings
2. Verify model is configured in `config/models_config.yaml`
3. Check API key for the selected provider
4. Review `logs/server.log` for errors
5. Ensure trigger threshold is met (count conversation rounds)

### Wrong Model Being Used

1. Navigate to Settings > Title Generation
2. Select correct model from dropdown
3. Save settings
4. Backend automatically reloads configuration

### Title Generation Too Slow

1. Reduce `max_context_rounds` (fewer tokens to process)
2. Switch to a faster model
3. Increase `timeout_seconds` if needed

## Future Enhancements (Not Implemented)

These features could be added in the future:

1. **Multi-language Support**: Detect conversation language and use appropriate prompt
2. **Title Editing**: Allow users to manually edit generated titles
3. **Title History**: Save and allow reverting to previous titles
4. **Batch Generation**: Generate titles for all existing conversations
5. **Cost Dashboard**: Show cumulative cost of title generation
6. **Custom Prompts per Assistant**: Different prompt templates for different assistants

## Code Quality

- ✅ Type hints throughout
- ✅ Comprehensive error handling
- ✅ Logging at all levels
- ✅ Async/await best practices
- ✅ No blocking operations in main flow
- ✅ Clean separation of concerns
- ✅ Frontend/backend integration
- ✅ Responsive UI components

## Notes

- Configuration changes require backend restart (unless using the UI)
- Title generation happens in background, doesn't block user
- Frontend refreshes session list 1 second after streaming completes
- Only generates for conversations with default/truncated titles
- Supports all models configured in `models_config.yaml`
