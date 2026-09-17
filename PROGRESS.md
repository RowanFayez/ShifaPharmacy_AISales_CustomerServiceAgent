## Current state

M0–M3 are runtime-verified in the repository `.venv` (Python 3.12).
SQLite migration and seed complete: 6 categories, 40 products (8 Rx), 3 customers, and 15 bilingual knowledge documents.
The Flask-WTF M2 dashboard is covered by tests; M3 adds persistent Chroma, local multilingual E5 embeddings, Arabic normalization, cache invalidation, and KB CRUD sync.
M4 knowledge admin, LangGraph, chat, and Messenger remain unimplemented.

## Milestones

| Milestone | Status |
|---|---|
| M0 — Checklist, progress, scaffold, config, `.env.example` | DONE |
| M1 — Models, migrations, seed data, bilingual KB | DONE |
| M2 — Core admin pages | DONE |
| M3 — RAG and KB sync | DONE |
| M4 — Knowledge admin | NOT_STARTED |
| M5 — Tools and services | NOT_STARTED |
| M6 — LangGraph agent | NOT_STARTED |
| M7 — Chat and persistence | NOT_STARTED |
| M8 — Multilingual hardening and validation | NOT_STARTED |
| M9 — README, diagrams, fresh-clone verification | NOT_STARTED |
| M10 — Messenger bonus | NOT_STARTED |

## Last session

18 September 2026 · Installed Python 3.12 project venv, fixed M2 CSRF and SQLite-path defects, verified migration/seed and 8 tests · implemented M3 persistent Chroma RAG with E5 embedding cache, Arabic normalization, CRUD sync, reindex script, and real retrieval smoke test · configured verified fallback model `nex-agi/nex-n2.5-mini:free` · pushed M0–M3 to GitHub `main` (commit `c8a7013`).

## Open blockers

- `python`/`py` may require a new terminal session to use the newly installed system PATH; the repository `.venv\Scripts\python.exe` is verified.
- Local Hugging Face model download works anonymously but emits a rate-limit warning; `HF_TOKEN` is optional and not needed for the verified local cache.

## Next up

M4 — knowledge-management admin and index-status UI.
