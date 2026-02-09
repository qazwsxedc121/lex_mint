# API Endpoints Documentation

This document describes all available API endpoints in the FastAPI backend.

**Base URL:** `http://localhost:<API_PORT>` (configurable via API_PORT in .env)

**API Documentation:** `http://localhost:<API_PORT>/docs` (Swagger UI)

---

## Sessions API (`/api/sessions`)

### Create Session

**POST** `/api/sessions`

Create a new conversation session.

**Request Body:**
```json
{
  "assistant_id": "default",  // optional, defaults to "default"
  "model_id": "deepseek-chat" // optional, uses assistant's default model
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "assistant_id": "default",
  "model_id": "deepseek-chat",
  "created_at": "2026-01-25T14:30:00",
  "title": "New Conversation",
  "current_step": 0
}
```

### List Sessions

**GET** `/api/sessions`

Retrieve all conversation sessions.

**Response:**
```json
[
  {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "assistant_id": "default",
    "model_id": "deepseek-chat",
    "created_at": "2026-01-25T14:30:00",
    "title": "Python Performance",
    "current_step": 5
  }
]
```

### Get Session

**GET** `/api/sessions/{session_id}`

Get session details with full message history.

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "assistant_id": "default",
  "model_id": "deepseek-chat",
  "created_at": "2026-01-25T14:30:00",
  "title": "Python Performance",
  "current_step": 5,
  "messages": [
    {
      "role": "user",
      "content": "How to optimize Python code?",
      "timestamp": "2026-01-25T14:30:15"
    },
    {
      "role": "assistant",
      "content": "Here are some optimization techniques...",
      "timestamp": "2026-01-25T14:30:22"
    }
  ]
}
```

### Delete Session

**DELETE** `/api/sessions/{session_id}`

Delete a conversation session and its message history.

**Response:**
```json
{
  "status": "deleted",
  "session_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Update Session Model

**PATCH** `/api/sessions/{session_id}/model`

Change the model used in a session.

**Request Body:**
```json
{
  "model_id": "gpt-4"
}
```

**Response:**
```json
{
  "status": "updated",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "model_id": "gpt-4"
}
```

### Update Session Assistant

**PATCH** `/api/sessions/{session_id}/assistant`

Change the assistant used in a session.

**Request Body:**
```json
{
  "assistant_id": "coding-expert"
}
```

**Response:**
```json
{
  "status": "updated",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "assistant_id": "coding-expert"
}
```

---

## Chat API (`/api/chat`)

### Send Message (Streaming)

**POST** `/api/chat/stream`

Send a message and receive AI response as Server-Sent Events (SSE).

**Request Body:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "What is Python?",
  "truncate_after_index": null,  // optional: truncate messages after this index
  "skip_user_message": false     // optional: skip adding user message (for regeneration)
}
```

**Response:** Server-Sent Events stream

```
data: {"type": "token", "content": "Python"}
data: {"type": "token", "content": " is"}
data: {"type": "token", "content": " a"}
data: {"type": "done", "full_response": "Python is a high-level programming language..."}
```

### Delete Message

**DELETE** `/api/chat/{session_id}/messages/{message_index}`

Delete a specific message and all subsequent messages.

**Response:**
```json
{
  "status": "deleted",
  "deleted_count": 3
}
```

### Regenerate Message

**POST** `/api/chat/{session_id}/regenerate/{message_index}`

Regenerate assistant response at a specific index.

**Response:** Server-Sent Events stream (same format as `/api/chat/stream`)

---

## Models API (`/api/models`)

### List Models

**GET** `/api/models`

Get all available models from all enabled providers.

**Response:**
```json
[
  {
    "id": "deepseek-chat",
    "name": "DeepSeek Chat",
    "provider_id": "deepseek",
    "description": "DeepSeek's chat model",
    "context_window": 64000,
    "max_output_tokens": 4000,
    "supports_streaming": true,
    "supports_functions": true,
    "supports_vision": false,
    "pricing": {
      "input": 0.0001,
      "output": 0.0002,
      "currency": "USD",
      "unit": "1K tokens"
    }
  }
]
```

### Get Model

**GET** `/api/models/{model_id}`

Get details for a specific model.

**Response:**
```json
{
  "id": "deepseek-chat",
  "name": "DeepSeek Chat",
  "provider_id": "deepseek",
  "description": "DeepSeek's chat model",
  "context_window": 64000,
  "max_output_tokens": 4000,
  "supports_streaming": true,
  "supports_functions": true,
  "supports_vision": false,
  "pricing": {
    "input": 0.0001,
    "output": 0.0002,
    "currency": "USD",
    "unit": "1K tokens"
  }
}
```

### Create Model

**POST** `/api/models`

Add a new model to the configuration.

**Request Body:**
```json
{
  "id": "gpt-4-turbo",
  "name": "GPT-4 Turbo",
  "provider_id": "openai",
  "description": "Latest GPT-4 Turbo model",
  "context_window": 128000,
  "max_output_tokens": 4096,
  "supports_streaming": true,
  "supports_functions": true,
  "supports_vision": true,
  "pricing": {
    "input": 0.01,
    "output": 0.03,
    "currency": "USD",
    "unit": "1K tokens"
  }
}
```

### Update Model

**PUT** `/api/models/{model_id}`

Update model configuration.

**Request Body:** Same as Create Model

### Delete Model

**DELETE** `/api/models/{model_id}`

Remove a model from the configuration.

### Refresh Models

**POST** `/api/models/refresh`

Reload model configuration from YAML file.

**Response:**
```json
{
  "status": "refreshed",
  "models_count": 15
}
```

---

## Assistants API (`/api/assistants`)

### List Assistants

**GET** `/api/assistants`

Get all available assistants.

**Response:**
```json
[
  {
    "id": "default",
    "name": "Default Assistant",
    "description": "General purpose assistant",
    "system_prompt": "You are a helpful AI assistant.",
    "default_model_id": "deepseek-chat",
    "temperature": 0.7,
    "max_tokens": 4000
  }
]
```

### Get Assistant

**GET** `/api/assistants/{assistant_id}`

Get details for a specific assistant.

### Create Assistant

**POST** `/api/assistants`

Create a new assistant.

**Request Body:**
```json
{
  "id": "coding-expert",
  "name": "Coding Expert",
  "description": "Expert in software development",
  "system_prompt": "You are an expert software developer...",
  "default_model_id": "deepseek-chat",
  "temperature": 0.3,
  "max_tokens": 4000
}
```

### Update Assistant

**PUT** `/api/assistants/{assistant_id}`

Update assistant configuration.

### Delete Assistant

**DELETE** `/api/assistants/{assistant_id}`

Remove an assistant from the configuration.

---

## Health Check

### Health

**GET** `/api/health`

Check API health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-25T14:30:00"
}
```

---

## Error Responses

All endpoints may return error responses in the following format:

**400 Bad Request:**
```json
{
  "detail": "Invalid request parameters"
}
```

**404 Not Found:**
```json
{
  "detail": "Session not found"
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Internal server error message"
}
```

---

## CORS Configuration

The API supports CORS with the following origins by default:
- `http://localhost:5173` (Vite dev server)
- `http://localhost:3000`
- Configurable via `CORS_ORIGINS` environment variable

---

## Authentication

Currently, the API does not implement authentication. All endpoints are publicly accessible on localhost.

**Note:** Add authentication before deploying to production.
