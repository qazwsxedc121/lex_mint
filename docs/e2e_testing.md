# E2E Testing Guide (Playwright)

This project has Playwright e2e tests in `frontend/tests/e2e/specs/`.

## Scope

- Chat + LLM smoke test: `frontend/tests/e2e/specs/chat-llm-smoke.spec.ts`
- Group chat flows: `frontend/tests/e2e/specs/group-chat.spec.ts`
- Other UI smoke tests: `frontend/tests/e2e/specs/*.spec.ts`

## Prerequisites

1. Root `.env` has both ports configured:
   - `API_PORT=<API_PORT>`
   - `FRONTEND_PORT=<FRONTEND_PORT>`
2. Keys/models are available for real LLM reply (for chat smoke test).
3. Frontend dependencies are installed:

```powershell
cd frontend
npm install
```

## Port Handling (Two Cases)

Use this check before running e2e:

```powershell
$apiPort = [int](Get-Content ..\.env | Select-String '^API_PORT=' | ForEach-Object { $_.Line.Split('=')[1] })
$fePort = [int](Get-Content ..\.env | Select-String '^FRONTEND_PORT=' | ForEach-Object { $_.Line.Split('=')[1] })

$apiListening = Get-NetTCPConnection -LocalPort $apiPort -State Listen -ErrorAction SilentlyContinue
$feListening = Get-NetTCPConnection -LocalPort $fePort -State Listen -ErrorAction SilentlyContinue

"API: " + ($(if ($apiListening) { "LISTEN" } else { "FREE" }))
"FE: " + ($(if ($feListening) { "LISTEN" } else { "FREE" }))
```

- If port is **LISTEN**: service is already running, Playwright will reuse it.
- If port is **FREE**: Playwright will auto-start missing backend/frontend via `webServer` config.

## Run The Chat + LLM Smoke Test

From `frontend/`:

```powershell
npx playwright test tests/e2e/specs/chat-llm-smoke.spec.ts --project=chromium --workers=1
```

This test will:
- create a chat session via API
- send one user message in chat UI
- wait for one real assistant reply (not just "Generating...")
- print user/assistant text in test output
- clean up the session

## Useful Commands

```powershell
# Run all e2e tests
npx playwright test

# Open Playwright UI mode
npx playwright test --ui

# Open HTML report
npx playwright show-report
```

