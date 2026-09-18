## Current state

M0–M6 are runtime-verified in the repository `.venv` (Python 3.12).
SQLite migration and seed complete: 6 categories, 40 products (8 Rx), 3 customers, and 15 bilingual knowledge documents.
The Flask-WTF dashboard now includes knowledge-document CRUD, per-document index status, and a reindex action; its index synchronization is covered by offline tests.
M5 adds validated, service-backed pharmacy tools; M6 adds a stateful LangGraph with SQLite checkpoints and deterministic Rx, confirmation, and safety gates. Chat and Messenger remain unimplemented.

## Milestones

| Milestone | Status |
|---|---|
| M0 — Checklist, progress, scaffold, config, `.env.example` | DONE |
| M1 — Models, migrations, seed data, bilingual KB | DONE |
| M2 — Core admin pages | DONE |
| M3 — RAG and KB sync | DONE |
| M4 — Knowledge admin | DONE |
| M5 — Tools and services | DONE |
| M6 — LangGraph agent | DONE |
| M7 — Chat and persistence | NOT_STARTED |
| M8 — Multilingual hardening and validation | NOT_STARTED |
| M9 — README, diagrams, fresh-clone verification | NOT_STARTED |
| M10 — Messenger bonus | NOT_STARTED |

## Last session

18 September 2026 · Installed declared LangGraph dependencies and completed M5/M6. Validated tools call transaction-safe services; a real order decrements stock and Rx orders are rejected. LangGraph branches through safety, Rx, confirmation, and tool execution with SQLite checkpoints. Full suite: 16 passed.

## Open blockers

- `python`/`py` may require a new terminal session to use the newly installed system PATH; the repository `.venv\Scripts\python.exe` is verified.
- Local Hugging Face model download works anonymously but emits a rate-limit warning; `HF_TOKEN` is optional and not needed for the verified local cache.

## Next up

M7 — chat UI, API, and conversation persistence.
