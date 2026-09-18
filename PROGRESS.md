## Current state

M0–M4 are runtime-verified in the repository `.venv` (Python 3.12).
SQLite migration and seed complete: 6 categories, 40 products (8 Rx), 3 customers, and 15 bilingual knowledge documents.
The Flask-WTF dashboard now includes knowledge-document CRUD, per-document index status, and a reindex action; its index synchronization is covered by offline tests.
M3 adds persistent Chroma, local multilingual E5 embeddings, Arabic normalization, cache invalidation, and KB CRUD sync. LangGraph, chat, and Messenger remain unimplemented.

## Milestones

| Milestone | Status |
|---|---|
| M0 — Checklist, progress, scaffold, config, `.env.example` | DONE |
| M1 — Models, migrations, seed data, bilingual KB | DONE |
| M2 — Core admin pages | DONE |
| M3 — RAG and KB sync | DONE |
| M4 — Knowledge admin | DONE |
| M5 — Tools and services | NOT_STARTED |
| M6 — LangGraph agent | NOT_STARTED |
| M7 — Chat and persistence | NOT_STARTED |
| M8 — Multilingual hardening and validation | NOT_STARTED |
| M9 — README, diagrams, fresh-clone verification | NOT_STARTED |
| M10 — Messenger bonus | NOT_STARTED |

## Last session

18 September 2026 · Re-verified M0–M3: clean migration/seed produced 6 categories, 40 products (8 Rx), 3 customers, and 15 knowledge documents; reindex rebuilt 15 documents; live delivery retrieval scored 0.8782. Reconciled stale Git evidence: the baseline was `0fcfa4e`, not `c8a7013`. Primary OpenRouter tool-call and structured-JSON probes passed. Completed and published M4 knowledge CRUD, status, and reindex UI; targeted tests passed and full suite is 10 passed.

## Open blockers

- `python`/`py` may require a new terminal session to use the newly installed system PATH; the repository `.venv\Scripts\python.exe` is verified.
- Local Hugging Face model download works anonymously but emits a rate-limit warning; `HF_TOKEN` is optional and not needed for the verified local cache.

## Next up

M5 — business tools and service layer.
