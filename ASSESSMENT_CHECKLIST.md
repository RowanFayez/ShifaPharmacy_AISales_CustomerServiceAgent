# Assessment checklist

Source of truth: `docs/assessment.pdf`. Evidence is added only after a command, test, or screenshot exists.

| # | Requirement (verbatim intent) | Source section | Mandatory / Bonus | Status | Implementation location | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Select a suitable business domain for the agent. | Overview | Mandatory | DONE | `README.md` | `M0 structural check: PASS` | Shifa Pharmacy selected. |
| 2 | Build a working AI sales and customer-service agent. | Overview | Mandatory | NOT_STARTED | — | — | |
| 3 | Answer customer questions. | Overview | Mandatory | NOT_STARTED | — | — | |
| 4 | Retrieve information using RAG. | Overview | Mandatory | NOT_STARTED | — | — | |
| 5 | Perform business actions through tools/functions. | Overview | Mandatory | NOT_STARTED | — | — | |
| 6 | Understand customer questions. | 1. AI Agent / Customer Service | Mandatory | NOT_STARTED | — | — | |
| 7 | Answer questions about the business. | 1. AI Agent / Customer Service | Mandatory | NOT_STARTED | — | — | |
| 8 | Retrieve relevant information from the business knowledge base. | 1. AI Agent / Customer Service | Mandatory | NOT_STARTED | — | — | |
| 9 | Handle basic customer-service conversations. | 1. AI Agent / Customer Service | Mandatory | NOT_STARTED | — | — | |
| 10 | Maintain enough conversation context for coherent responses. | 1. AI Agent / Customer Service | Mandatory | NOT_STARTED | — | — | |
| 11 | Recommend relevant products/services. | 1. AI Agent / Sales | Mandatory | NOT_STARTED | — | — | |
| 12 | Answer questions about products/services. | 1. AI Agent / Sales | Mandatory | NOT_STARTED | — | — | |
| 13 | Provide prices and other available information. | 1. AI Agent / Sales | Mandatory | NOT_STARTED | — | — | |
| 14 | Help the customer make a decision. | 1. AI Agent / Sales | Mandatory | NOT_STARTED | — | — | |
| 15 | Perform at least one real business action. | 1. AI Agent / Sales | Mandatory | NOT_STARTED | — | — | |
| 16 | Use RAG in the agent. | 2. RAG | Mandatory | DONE | `agent/rag.py`, `app/services/kb_service.py` | `pytest -q` → 8 passed; `scripts/reindex_kb.py` | Persistent Chroma derives from SQL knowledge rows. |
| 17 | Keep business-relevant information in the knowledge base. | 2. RAG | Mandatory | DONE | `data/knowledge/`, `scripts/seed_db.py` | Seed verification → 15 documents; `scripts/reindex_kb.py` → 15 indexed | Bilingual source documents are seeded into `KnowledgeDocument`. |
| 18 | Retrieve relevant knowledge-base information when answering customers. | 2. RAG | Mandatory | DONE | `agent/rag.py` | Real smoke test: delivery-fee query → `Delivery areas and fees` | Agent integration is deferred to M6. |
| 19 | Allow an administrator to add knowledge/data. | 2. RAG / RAG Management | Mandatory | NOT_STARTED | — | — | |
| 20 | Allow an administrator to update existing knowledge/data. | 2. RAG / RAG Management | Mandatory | NOT_STARTED | — | — | |
| 21 | Allow an administrator to delete knowledge/data. | 2. RAG / RAG Management | Mandatory | NOT_STARTED | — | — | |
| 22 | Use updated knowledge/data in the agent retrieval process. | 2. RAG / RAG Management | Mandatory | NOT_STARTED | — | — | |
| 23 | Implement the agent using LangGraph. | 3. LangGraph | Mandatory | NOT_STARTED | — | — | |
| 24 | Give the LangGraph a meaningful workflow, not one LLM call. | 3. LangGraph | Mandatory | NOT_STARTED | — | — | |
| 25 | Perform an action using a tool/function. | 4. Business Action / Function Calling | Mandatory | NOT_STARTED | — | — | |
| 26 | Make the tool/function action appropriate to the selected business. | 4. Business Action / Function Calling | Mandatory | NOT_STARTED | — | — | |
| 27 | Make the action interact with the backend/database rather than return a fake LLM response. | 4. Business Action / Function Calling | Mandatory | NOT_STARTED | — | — | |
| 28 | Build an administration dashboard using Flask and Flask templates. | 5. Flask Dashboard | Mandatory | DONE | `app/blueprints/admin/`, `app/templates/admin/` | `pytest -q` → 8 passed | M2 routes are runtime-tested; knowledge routes are M4. |
| 29 | Let an administrator see and manage the system. | 5. Flask Dashboard | Mandatory | DONE | `app/blueprints/admin/routes.py` | `pytest -q` → 8 passed | M2 scope covers categories, products, orders, and customers. |
| 30 | Display business data relevant to the selected business. | 5. Flask Dashboard / Business Data | Mandatory | DONE | `app/templates/admin/` | `pytest -q` → 8 passed | Core business data routes are tested. |
| 31 | Let an administrator view RAG data. | 5. Flask Dashboard / RAG Data Management | Mandatory | NOT_STARTED | — | — | |
| 32 | Let an administrator add RAG data. | 5. Flask Dashboard / RAG Data Management | Mandatory | NOT_STARTED | — | — | |
| 33 | Let an administrator edit RAG data. | 5. Flask Dashboard / RAG Data Management | Mandatory | NOT_STARTED | — | — | |
| 34 | Let an administrator delete RAG data. | 5. Flask Dashboard / RAG Data Management | Mandatory | NOT_STARTED | — | — | |
| 35 | Demonstrate knowledge-base management without source-code changes. | 5. Flask Dashboard / RAG Data Management | Mandatory | NOT_STARTED | — | — | |
| 36 | Use a database. | 6. Database | Mandatory | DONE | `app/config.py`, `migrations/` | `flask db upgrade`; seeded DB count verification | SQLite database migrated and seeded. |
| 37 | Use an ORM. | 6. Database | Mandatory | DONE | `app/models/`, `app/extensions.py` | `pytest -q` → 8 passed | SQLAlchemy 2.x typed models. |
| 38 | Store required business entities. | 6. Database | Mandatory | DONE | `app/models/catalog.py`, `app/models/sales.py` | Seed count verification | 6 categories, 40 products, 3 customers, sample order. |
| 39 | Store agent-related data. | 6. Database | Mandatory | DONE | `app/models/knowledge.py`, `app/models/chat.py` | Seed count verification; `pytest -q` → 8 passed | Knowledge, conversation, message, and handoff tables are migrated. |
| 40 | Use Python for the backend. | 7. Required Technology Stack / Backend | Mandatory | DONE | `app/`, `scripts/` | Python 3.12 venv; `pytest -q` → 8 passed | |
| 41 | Use Flask for the backend. | 7. Required Technology Stack / Backend | Mandatory | DONE | `app/__init__.py`, `app/blueprints/` | `pytest -q` → 8 passed | |
| 42 | Use LangGraph for the AI implementation. | 7. Required Technology Stack / AI | Mandatory | NOT_STARTED | — | — | |
| 43 | Use RAG for the AI implementation. | 7. Required Technology Stack / AI | Mandatory | DONE | `agent/rag.py`, `app/services/kb_service.py` | `pytest -q` → 8 passed; real Chroma smoke test | Graph integration is deferred to M6. |
| 44 | Use an LLM. | 7. Required Technology Stack / AI | Mandatory | NOT_STARTED | — | — | M6 integration pending. |
| 45 | Use an embedding model. | 7. Required Technology Stack / AI | Mandatory | DONE | `agent/llm.py` | `scripts/reindex_kb.py` → 15 indexed | Local `intfloat/multilingual-e5-small`. |
| 46 | Use a vector database or retrieval system. | 7. Required Technology Stack / AI | Mandatory | DONE | `agent/rag.py` | `scripts/reindex_kb.py`; real retrieval smoke test | Persistent ChromaDB. |
| 47 | Use Flask templates in the frontend. | 7. Required Technology Stack / Frontend | Mandatory | DONE | `app/templates/` | `pytest -q` → 8 passed | |
| 48 | Use HTML in the frontend. | 7. Required Technology Stack / Frontend | Mandatory | DONE | `app/templates/` | `pytest -q` → 8 passed | |
| 49 | Use CSS in the frontend. | 7. Required Technology Stack / Frontend | Mandatory | DONE | `app/static/css/admin.css` | `pytest -q` → 8 passed | |
| 50 | Use JavaScript where needed in the frontend. | 7. Required Technology Stack / Frontend | Mandatory | NOT_STARTED | — | — | |
| 51 | Submit a GitHub repository containing the complete project. | 9. Deliverables / GitHub Repository | Mandatory | NOT_STARTED | — | — | External publication required. |
| 52 | Include source code in the submitted repository. | 9. Deliverables / GitHub Repository | Mandatory | NOT_STARTED | — | — | |
| 53 | Include database models in the submitted repository. | 9. Deliverables / GitHub Repository | Mandatory | NOT_STARTED | — | — | |
| 54 | Include the agent/LangGraph implementation in the submitted repository. | 9. Deliverables / GitHub Repository | Mandatory | NOT_STARTED | — | — | |
| 55 | Include the RAG implementation in the submitted repository. | 9. Deliverables / GitHub Repository | Mandatory | NOT_STARTED | — | — | |
| 56 | Include the Flask dashboard in the submitted repository. | 9. Deliverables / GitHub Repository | Mandatory | NOT_STARTED | — | — | |
| 57 | Include tool/function implementations in the submitted repository. | 9. Deliverables / GitHub Repository | Mandatory | NOT_STARTED | — | — | |
| 58 | Include requirements/dependencies in the submitted repository. | 9. Deliverables / GitHub Repository | Mandatory | IMPLEMENTED — NOT FULLY VERIFIED | `requirements.txt` | `M0 structural check: PASS` | Manifest exists; this workspace is not yet a submitted GitHub repository. |
| 59 | Include a README explaining business, architecture, LangGraph, RAG, DB, tools, local run, env vars, conversations, limitations, and assumptions. | 9. Deliverables / README | Mandatory | NOT_STARTED | `README.md` | — | Atomic README topics will be checked in M9. |
| 60 | Provide a runnable demo: conversation, understanding, RAG response, real action, dashboard result, and dashboard data updates. | 9. Deliverables / Demo | Mandatory | NOT_STARTED | — | — | |
| 61 | Be able to explain, test, and modify the implementation in the interview. | 10. AI Usage Policy | Mandatory | NOT_STARTED | `docs/DECISIONS.md` | — | |
| 62 | Integrate with Facebook Page / Meta Messenger. | 8. Bonus — Meta Integration | Bonus | NOT_STARTED | — | — | Only after mandatory work. |
