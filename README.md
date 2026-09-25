# GPS ATLAS

**Information Intelligence & Document Protection Platform for GPS Renewables**

> "GPS ATLAS ensures that critical information is never lost, while making the right information instantly discoverable to the right people."

This is a working, end-to-end implementation of the GPS ATLAS concept submitted to **GPS Ignite**: a secure document depository with an AI search assistant that answers questions in plain English and cites the exact source document for every claim, strictly filtered by what each person is authorized to see.

It is a real, running application — not a mockup. Every feature described below has been built, tested, and verified against real uploaded PDFs, DOCX, XLSX and PPTX files.

---

## 1. What it does

- **Single secure depository.** Every department (Legal, Engineering, Procurement, Finance, Projects, Founder's Office, or any you add) uploads contracts, POs, BOQs, drawings, MOMs, datasheets, reports and O&M records into one place, with full version history.
- **Ask ATLAS.** Type a question in plain English. The AI reads only the documents you're authorized to view, answers it, and tags every factual sentence with a clickable citation back to the exact source file and page.
- **Viewer ID access control.** Every document and every AI answer is filtered by who is asking — role (Employee / Manager / Admin), department, explicit cross-department grants, and individual per-document access grants. Access is enforced server-side, in the database query itself, before a single sentence is ever scored or shown — never trusted to the frontend.
- **Citation Verification Layer.** Every AI-generated sentence must carry a citation marker that resolves to a document the user actually retrieved. Anything that doesn't is flagged as *unverified* in the UI rather than silently presented as fact.
- **Encrypted at rest.** Every uploaded file is encrypted before it touches disk. The encryption key is generated on first run and never stored in the database.
- **Full audit trail.** Every login, upload, download, search, and admin action is logged, timestamped, and reviewable by administrators.
- **Version history & duplicate detection.** Upload a revised contract as a "new version" and the old one is kept, not lost. ATLAS also flags exact and near-duplicate documents so the same file doesn't end up scattered under two titles.
- **Expiry tracking.** ATLAS scans uploaded contracts/POs for expiry, validity and termination dates and surfaces "expiring soon" on the dashboard — always labelled as detected vs. manually confirmed, never presented as legal certainty.
- **Analytics dashboard.** Documents by department/type, storage used, upload activity, and duplicate/expiry flags, for the Founder's Office view described in the original pitch.

## 2. Why it's designed this way (and why that matters for the judging criteria)

**Runs entirely on itself — no paid API required.** The retrieval and answer-synthesis pipeline is fully local by default:
- **Retrieval** uses a hybrid of BM25 (keyword/lexical search) and a local embedding model, so search quality doesn't depend on any external service being reachable.
- **Answer synthesis** defaults to an **extractive** mode: it assembles the answer out of verbatim sentences copied from the retrieved, authorized documents. No text is generated, so hallucination is *structurally* impossible in this mode — not just prompted against.
- The AI layer is **pluggable**: set an OpenAI, Anthropic, or Azure OpenAI API key (or point it at a local Ollama server) in `backend/.env` and answers upgrade automatically to natural-language synthesis, while the same Citation Verification Layer still checks every sentence. No code changes needed either way. See `backend/.env.example`.

This means the app can be demoed on a laptop with no internet connection and no API keys, and it never has a "the demo broke because the API was down/rate-limited/expensive" failure mode — while still supporting a best-in-class hosted model if the judges want to see that.

**Security is enforced in one place, not scattered.** `backend/app/deps.py` has a single function, `can_view_document()`, that is the one and only source of truth for whether a user can see a document. Every route — search, ask, download, metadata — calls it. There is no path in the codebase where document text reaches a user without passing through this check first.

**Stable by construction, not by luck.**
- Passwords are hashed with bcrypt; never stored or logged in plaintext.
- Repeated failed logins temporarily lock the account (configurable).
- JWT-based sessions with configurable expiry.
- Files are encrypted at rest with a server-held key that's generated once and stored outside the database, so a stolen database file alone doesn't leak documents.
- The local embedding index uses a deterministic hash function (not Python's randomized `hash()`), so the search index survives a server restart without silently going stale — a subtle bug that would otherwise corrupt every existing document's searchability after a routine deploy.
- SQLite + local file storage means zero external infrastructure to misconfigure for a hackathon demo, while the code is written against SQLAlchemy so swapping in Postgres for a real multi-site deployment is a one-line config change.

## 3. Architecture

Frontend (React/Vite) -> REST (JWT bearer) -> FastAPI backend
  Phase 1 (Document Depository & Processing): upload, encrypt at rest, extract text, chunk + embed, duplicate check, expiry detect
  Phase 2 (AI Search & Synthesis): Viewer ID permission check (deps.py) -> hybrid BM25 + cosine retrieval, scoped BEFORE ranking -> extractive/hosted/Ollama synthesis + Citation Verification Layer
  Storage: SQLite (SQLAlchemy) for users/departments/documents/versions/chunks+embeddings/audit log; encrypted file store (Fernet) on disk

This maps directly onto the two-phase flow from the original ATLAS design: **Phase 1 (Document Depository & Processing)** — upload, metadata & Viewer ID tagging, text extraction & chunking, embeddings, storage — and **Phase 2 (AI Search & Synthesis)** — query, Viewer ID verification, access-controlled search, AI summarization, citation verification, final cited answer.

### Key backend modules
| Path | Responsibility |
|---|---|
| `app/models.py` | Database schema: users, departments, documents, versions, chunks, access grants, audit log |
| `app/deps.py` | **The single source of truth for access control** (`can_view_document`, `accessible_document_filter`) |
| `app/services/extraction.py` | Text extraction for PDF, DOCX, XLSX, PPTX, CSV, images (OCR), legacy formats via LibreOffice |
| `app/services/chunking.py` | Page-aware chunking with overlap, so citations can point at a page number |
| `app/services/embeddings.py` | Local, offline embedding backend (hashing trick by default; auto-upgrades to a neural model if `sentence-transformers` + cached weights are present) |
| `app/services/retrieval.py` | Hybrid BM25 + cosine retrieval, scoped to authorized documents *before* scoring |
| `app/services/llm.py` | Pluggable answer synthesis (extractive / OpenAI / Anthropic / Azure / Ollama) + Citation Verification Layer |
| `app/services/duplicates.py` | Exact (SHA-256) and near-duplicate (embedding similarity) detection |
| `app/services/expiry.py` | Regex + fuzzy date parsing to detect contract/PO expiry dates |
| `app/services/storage.py` | Encrypted-at-rest file storage |
| `app/routers/*` | REST API: auth, users, departments, documents, search/ask, admin |

### Key frontend pages
| Path | Purpose |
|---|---|
| `pages/Login.jsx` | Sign in |
| `pages/Dashboard.jsx` | Overview, quick-ask, expiring documents, recent activity |
| `pages/Ask.jsx` | The core "Ask ATLAS" chat interface with clickable citations |
| `pages/Library.jsx` + `components/UploadModal.jsx` + `components/DocumentDrawer.jsx` | Browse/filter/upload/version/archive documents |
| `pages/admin/Users.jsx` | User & department management |
| `pages/admin/AuditLog.jsx` | Full activity log |
| `pages/admin/Analytics.jsx` | Org-wide charts |

## 4. Running it

**Requirements:** Python 3.11+, Node 18+, and (optionally) `tesseract` on PATH for OCR of scanned documents. Nothing else — no Docker, no external database, no API key.

### Easiest: one command
```bash
./start.sh          # macOS / Linux
start.bat           # Windows
```
This creates a virtualenv, installs dependencies, builds the frontend, and starts the whole app at **http://localhost:8000** as a single process (FastAPI serves the built React app directly).

### First login
```
Email:    admin@gpsrenewables.com
Password: ChangeMe!2026
```
You'll be forced to set a new password immediately (this is enforced by the backend, not just a UI nag). The app seeds a handful of realistic demo documents (a vendor supply agreement, a weekly progress report, an MOM, and a security policy doc) across different departments so there's something to search on first launch — delete/archive them from the Library once you're loading real documents.

### Manual / development setup
```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # optional: add an LLM API key here
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal, hot-reload dev server on :5173, proxies /api to :8000)
cd frontend
npm install
npm run dev
```

### Running with a real AI model instead of extractive mode
Add **one** of these blocks to `backend/.env` and restart:
```
ATLAS_OPENAI_API_KEY=sk-...
```
or run a local model with [Ollama](https://ollama.com) (`ollama pull llama3.1`) — no key needed, still fully offline. See `.env.example` for every option.

## 5. Security model in detail (the "Viewer ID" system)

Every document has:
- an **owning department** (whoever uploaded it into),
- an optional list of **additional departments** granted view access,
- an optional list of **roles** granted org-wide view access (e.g. "every Manager can see this, regardless of department" — used for the Founder's Office cross-department visibility described in the original pitch),
- and optional **individual grants** to a specific person (for the one-off "give this one Finance analyst access to this one Legal contract" case).

A user can see a document if **any** of the following is true: they're an Admin; the document belongs to their department; their department is in the document's extra-department list; their role is in the document's allowed-roles list; or they hold an individual grant. This is evaluated as a **SQL filter**, so an unauthorized document is excluded from the query itself — it never gets loaded, scored by the search engine, or handed to the AI model.

This was tested end-to-end during development: an Engineering employee could not download, search, or receive AI answers built from a Founder's Office policy document until explicitly granted access, at which point it correctly became visible everywhere (list, search, ask, download) simultaneously.

## 6. What's stubbed vs. production-grade, honestly

This was built for the GPS Ignite build stage, so it's worth being explicit about what would change for a full multi-site production rollout:

- **Database:** SQLite is used for zero-config reliability in a demo/single-office setting. The code is plain SQLAlchemy, so pointing `ATLAS_DATABASE_URL` at Postgres is the only change needed for concurrent multi-writer scale.
- **Department/role JSON filters:** for simplicity, a document's extra-department and extra-role grants are stored as JSON arrays matched with SQL `LIKE`. This is correct and fast at the scale a pilot would see (thousands of documents); a proper join table is a natural next step for very large document counts.
- **Background processing:** text extraction/embedding currently runs synchronously on upload. For very large files (hundreds of pages) this should move to a background task queue (Celery/RQ) — the pipeline in `services/ingestion.py` is already factored as one call so this is a drop-in change, not a rewrite.
- **Neural embeddings:** the app runs on a fast, dependency-light hashing embedder by default. Installing `sentence-transformers` (commented out in `requirements.txt`) upgrades retrieval to a real neural embedding model automatically, with no code change — it's auto-detected at startup.

## 7. Project structure
```
gps-atlas/
├── start.sh / start.bat        # one-command launcher
├── backend/
│   ├── app/                    # FastAPI application (see table above)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/                    # React application (see table above)
│   └── package.json
└── README.md                    # this file
```

---
Built for **GPS Ignite** by Shivam Sodhani, GPS Renewables Private Limited.
