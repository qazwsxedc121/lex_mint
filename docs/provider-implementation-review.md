# Provider Implementation Review

Date: 2026-02-19
Scope: backend provider abstraction, settings UI, provider CRUD/test flow.

## Findings

### 1) `protocol` is user-facing but behaves like an internal technical field (High)
- UI exposes `protocol` as a normal required field for provider editing.
- Runtime adapter selection for builtin providers is mostly driven by `sdk_class`, not by editable `protocol`.
- API key requirement logic is currently protocol-based (`ollama` exception), which can conflict with real adapter behavior.
- Risk: user confusion ("I changed protocol but behavior did not change"), and inconsistent validation.

References:
- `frontend/src/modules/settings/config/providers.config.tsx`
- `src/providers/registry.py`
- `src/api/services/model_config_service.py`

### 2) Test connection button is disabled only by `has_api_key` (High)
- Current UI disables test action when API key is missing.
- This blocks valid no-key local providers (for example Ollama).
- Risk: user cannot validate local provider setup from UI.

Reference:
- `frontend/src/modules/settings/config/providers.config.tsx`

### 3) Protocol options are hardcoded in frontend while backend already exposes `/protocols` (High)
- Frontend protocol select list is static.
- Backend has an endpoint for supported protocols.
- Risk: drift between UI and backend capability over time.

References:
- `frontend/src/modules/settings/config/providers.config.tsx`
- `frontend/src/services/api.ts`
- `src/api/routers/models.py`

### 4) Parameter support matrix is static and appears out-of-sync with adapters (Medium)
- UI parameter visibility uses a static mapping.
- Adapter implementations support parameters not reflected in the static map (example: Gemini has `max_tokens`, `top_p`, `top_k` mapping in adapter code).
- Risk: parameters hidden in UI even when backend supports them.

References:
- `frontend/src/shared/constants/paramSupport.ts`
- `src/providers/adapters/gemini_adapter.py`

### 5) Provider test UX relies on `window.prompt` / `alert` (Medium)
- Test flow uses browser-native prompt/alert and hardcoded strings.
- This is inconsistent with app UX and localization quality.
- Risk: poor usability and maintainability.

Reference:
- `frontend/src/modules/settings/config/providers.config.tsx`

### 6) Data model includes `api_keys` rotation concept but runtime uses single key path (Medium)
- Types/config include `api_keys: List[str]`.
- Runtime read/write logic uses one key entry (`providers.<id>.api_key`).
- Risk: concept mismatch and extra cognitive load.

References:
- `src/api/models/model_config.py`
- `src/providers/types.py`
- `src/api/services/model_config_service.py`

## UX Note: "protocol" terminology

Current terminology is technical and may not be intuitive for general users.

Suggested direction:
- Rename UI label from "API Protocol" to "Compatibility Type" (advanced).
- Keep default as "OpenAI-compatible (recommended)".
- Hide or lock this field for builtin providers.
- Optionally auto-suggest compatibility type from `base_url`.

## Discussion Starters

1. Keep `protocol` as an internal field and expose only simple presets in UI.
2. For custom providers, provide a guided wizard: base URL -> auth -> compatibility.
3. Replace static capability maps with backend-provided capability metadata.

## Agreed Requirements (2026-02-19)

### Product behavior
- Provider setup should be "no protocol knowledge required" for normal users.
- Keep protocol-like controls in advanced options only (collapsed by default).
- Default routing policy:
  - Anthropic native -> native adapter path
  - Gemini native -> native adapter path
  - Ollama native -> native adapter path
  - OpenAI official -> `responses` by default
  - Other OpenAI-compatible providers -> `chat/completions` by default

### OpenAI official detection
- Use primary rule: provider id indicates OpenAI official.
- Add fallback rule: detect OpenAI official by `base_url` domain match (for example `api.openai.com`).

### Reliability
- Enable automatic fallback by default: if `responses` call fails in compatible scenarios, retry with `chat/completions`.
- Record fallback events in logs for troubleshooting and future tuning.

### UI/UX
- Advanced section remains collapsed by default.
- Users can override default routing behavior in advanced settings.
- Connection test action must not be blocked only by `has_api_key`; local no-key providers should still be testable.

### Compatibility and migration
- Keep legacy `protocol` field for backward compatibility for at least one major version.
- Introduce new internal routing fields progressively; old configs must continue to work without manual migration.
