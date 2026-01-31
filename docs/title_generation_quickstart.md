# Quick Start Guide - Title Generation Feature

This guide will help you quickly test the new title generation feature.

## Prerequisites

1. Backend dependencies installed (`./venv/Scripts/pip install -r requirements.txt`)
2. Frontend dependencies installed (`cd frontend && npm install`)
3. At least one model configured in `config/models_config.yaml`
4. API keys configured in `.env` file

## Quick Test (5 Minutes)

### Step 1: Verify Configuration (30 seconds)

Check that the configuration file exists and is valid:

```bash
cat config/title_generation_config.yaml
```

You should see:
```yaml
title_generation:
  enabled: true
  trigger_threshold: 1
  model_id: "openrouter:openai/gpt-4o-mini"
  ...
```

### Step 2: Run Tests (30 seconds)

```bash
./venv/Scripts/python test_title_generation.py
```

Expected: All tests pass with green OK messages.

### Step 3: Start Backend (1 minute)

```bash
./venv/Scripts/uvicorn src.api.main:app --reload --port 8888
```

Wait for:
```
INFO:     Application startup complete.
```

### Step 4: Start Frontend (1 minute)

In a new terminal:
```bash
cd frontend
npm run dev
```

Wait for:
```
  Local:   http://localhost:5173/
```

### Step 5: Configure Feature (1 minute)

1. Open browser: http://localhost:5173
2. Navigate to **Settings** (gear icon in sidebar)
3. Click **Title Generation** in settings sidebar
4. Verify settings:
   - [x] Enable automatic title generation
   - Trigger Threshold: **1**
   - Model: **openrouter:openai/gpt-4o-mini** (or any configured model)
5. Click **Save Settings**

### Step 6: Test Automatic Generation (2 minutes)

1. Navigate to **Chat** (chat icon in sidebar)
2. Create a new conversation (click "+" button)
3. Send a message: "Tell me about Paris"
4. Wait for AI response
5. **Watch the title**: After ~1 second, it should change from "New Conversation" to something like "Paris Overview" or "About Paris"

Success! The title was automatically generated.

### Step 7: Test Manual Regeneration (30 seconds)

1. In the same conversation, click the **Regenerate Title** button in the header
2. Title should update again (possibly to a different variation)

## Troubleshooting

### Title Didn't Generate

**Check logs:**
```bash
tail -f logs/server.log
```

Look for lines with `[TitleGen]`:
- `[TitleGen] Background title generation task created` - Good, task started
- `[TitleGen] Generated title: ...` - Good, title generated
- `[ERROR] [TitleGen] ...` - Problem, check error message

**Common issues:**
1. **Model not configured**: Add the model to `config/models_config.yaml`
2. **API key missing**: Add API key to `.env` file
3. **Feature disabled**: Check Settings > Title Generation > Enable checkbox
4. **Threshold not met**: Default is 1 round (2 messages total)

### Backend Won't Start

```bash
./venv/Scripts/python -c "import src.api.main"
```

If this fails, check:
- Python virtual environment activated
- All dependencies installed
- No syntax errors in code

### Frontend Shows Error

Check browser console (F12) for error messages.

Common fixes:
- Clear browser cache
- Restart frontend dev server
- Check API URL in `frontend/.env` (should be http://localhost:8888)

## Advanced Testing

### Change Trigger Threshold

Test with threshold = 2 (generates after 2 conversation rounds):

1. Settings > Title Generation
2. Set "Trigger Threshold" to **2**
3. Save Settings
4. Create new conversation
5. Send message, wait for response - **title should NOT change**
6. Send second message, wait for response - **title should change now**

### Use Different Model

1. Settings > Title Generation
2. Change "Model" dropdown to different model
3. Save Settings
4. Test generation - should use new model

### Customize Prompt

1. Settings > Title Generation
2. Edit "Prompt Template" textarea
3. Example custom prompt:
   ```
   Generate a creative, emoji-rich title (max 40 chars) for:
   {conversation_text}
   ```
4. Save Settings
5. Test generation - should see creative titles with emojis

## Viewing Generated Titles

Titles are stored in conversation markdown files:

```bash
cat conversations/your-assistant-name/YYYY-MM-DD/session-id.md
```

The frontmatter shows:
```yaml
---
title: "AI Generated Title Here"
...
---
```

## Next Steps

- Experiment with different models
- Customize the prompt template for your use case
- Adjust trigger threshold based on preference
- Monitor costs in logs (search for token usage)

## Getting Help

If you encounter issues:
1. Check `logs/server.log` for backend errors
2. Check browser console for frontend errors
3. Run `./venv/Scripts/python test_title_generation.py` to verify setup
4. Review `docs/title_generation_feature.md` for detailed documentation
