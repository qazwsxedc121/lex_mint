# Research Docs Index

Last updated: 2026-03-13

This directory stores research, competitor analysis, and historical strategy docs.
These files are reference material, not implementation source-of-truth.

Source-of-truth docs for current backend behavior:
- `docs/backend_refactor_plan.md`
- `docs/backend_module_responsibilities.md`
- `docs/flow_event_protocol_v1.md`
- `docs/api_endpoints.md`

## Structure

- `docs/research/competitors/` - product and architecture analysis of external tools
- `docs/research/rag/` - RAG-specific competitor and strategy analysis
- `docs/research/packaging/` - packaging proof-of-concept notes
- `docs/research/reports/` - dated deep-dive reports

## Maintenance Rule

When adding or updating a research doc:
- include date and scope at the top
- explicitly mark assumptions and version snapshot
- avoid using it as API/protocol truth unless synchronized with core docs
