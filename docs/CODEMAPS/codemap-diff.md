<!-- Generated: 2026-02-17 (Update #2) | Token estimate: ~400 -->

# Codemap Diff Report

## Status
INCREMENTAL UPDATE (changes <= 30%, updated in place)

## Changes Detected

### New Files
- `src/api/routers/prompt_templates.py` - CRUD for prompt templates
- `src/api/services/prompt_template_service.py` - YAML-backed template storage
- `src/api/services/rerank_service.py` - Model-based RAG reranking
- `src/api/models/prompt_template.py` - Pydantic schema with variable definitions
- `frontend/src/modules/settings/PromptTemplatesPage.tsx` - Config-driven CRUD
- `frontend/src/modules/settings/config/promptTemplates.config.tsx`
- `frontend/src/modules/settings/hooks/usePromptTemplates.ts`

### Modified Files
- `src/api/main.py` - Added prompt_templates router
- `src/api/services/agent_service_simple.py` - Prompt template + rerank integration
- `src/api/services/compression_service.py` - Hierarchical compression, language setting
- `frontend/src/shared/chat/` - Multiple component updates

## Updated Codemaps
| File | Changes |
|------|---------|
| architecture.md | Service count 35->37, added models layer, new design decisions |
| backend.md | Added prompt templates routes, rerank + template services |
| frontend.md | Settings sub-routes 13->14, added PromptTemplatesPage |
| data.md | Added prompt_templates_config.yaml state file |
| dependencies.md | No changes needed |

## New Features Since Last Scan
1. Prompt template system with JSON variable schema (text/number/boolean/select)
2. RAG reranking via model API (RerankService)
3. Hierarchical context compression with language setting
4. Template variable editor in frontend settings
