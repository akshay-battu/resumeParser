# TraqCheck Assignment — Build Prompt

Copy everything below the line into your AI coding assistant (Claude Code, Cursor, etc.) to generate the project. Sections in `[brackets]` are placeholders — fill in before sending.

---

## PROMPT

You are a senior full-stack engineer. Build a complete, working, submission-ready application called **TraqCheck** — a resume intake system where HR uploads a candidate's resume, the system extracts structured data from it, and an AI agent autonomously drafts and logs a personalized request to the candidate for their PAN and Aadhaar identity documents.

Treat this as a real deliverable that will be graded on code quality, correctness, and whether it actually runs — not a prototype. Ask me clarifying questions only if something below is genuinely ambiguous; otherwise make a reasonable choice and note the assumption in the README.

### 1. Tech Stack
- **Backend:** Python, Flask (preferred for speed) with a clean app-factory structure (`app/`, `routes/`, `models/`, `services/`)
- **Frontend:** React (Vite), functional components + hooks, no class components
- **Database:** SQLite for local dev, structured so switching to PostgreSQL only requires changing the connection string (use SQLAlchemy ORM)
- **AI/LLM:** Claude API (Anthropic) as primary, with an environment-variable-driven abstraction so the model can be swapped for OpenAI/OpenRouter without touching business logic
- **Agent orchestration:** keep it lightweight — a simple prompt-chained service is fine; don't force in LangChain if it adds boilerplate without value. If you do use LangChain, justify it in the README.
- **File storage:** local `/uploads` folder for dev, abstracted behind a storage service interface (so S3 could be swapped in later)

### 2. Backend — API Contract

Implement exactly these endpoints, with the specified request/response shapes:

**`POST /candidates/upload`**
- Accepts `multipart/form-data` with a `resume` file (PDF or DOCX only; reject others with `400`)
- Saves the file, kicks off parsing (synchronously is fine for this scope, but structure the parsing call as its own service function so it could be made async later)
- Returns `201` with `{ id, filename, status: "processing" | "parsed" | "failed" }`

**`GET /candidates`**
- Returns a list of all candidates: `id, name, email, phone, company, designation, status, created_at`
- Support optional `?status=` filter query param

**`GET /candidates/<id>`**
- Returns full parsed profile: `name, email, phone, company, designation, skills[]`, plus a **confidence score per field** (0–1 float) reflecting how certain the extraction was
- Include raw extracted text or a snippet if extraction partially failed, so the HR user isn't left with nothing

**`POST /candidates/<id>/request-documents`**
- Triggers the AI agent to generate a personalized message (email or SMS-style copy) requesting PAN and Aadhaar from the candidate, referencing their name/company/role naturally
- Logs the generated message + timestamp + channel to a `document_requests` table
- Returns the generated message content in the response so the frontend can display it immediately
- Does **not** need to actually send a real email/SMS — logging + returning the content satisfies the assignment, but structure the send step behind a `NotificationService` interface with a clearly stubbed `send()` method, so real delivery could be wired in later

**`POST /candidates/<id>/submit-documents`**
- Accepts `multipart/form-data` with `pan_document` and `aadhaar_document` image files (jpg/png/pdf)
- Validates file type and size (reject >10MB)
- Stores files, updates candidate status to `documents_submitted`
- Returns `200` with confirmation and file references

### 3. AI Agent Behavior (the core of the assignment — spend the most care here)

- **Resume parsing:** send extracted resume text to the LLM with a structured-output prompt (JSON mode / strict schema) to pull `name, email, phone, company, designation, skills[]`. Handle malformed LLM output gracefully — validate the JSON, retry once on failure, fall back to `null` fields with low confidence rather than crashing.
- **Confidence scoring:** derive confidence either from the LLM's own self-reported certainty (ask it to include this in the schema) or from simple heuristics (e.g., regex-validated email/phone = high confidence, inferred fields = lower). Be explicit in code comments about which approach you used and why.
- **Document request drafting:** this should read as a genuinely personalized, professional message — not a generic template with name inserted. Give the LLM the candidate's parsed context and instruct it to write naturally, explain *why* PAN/Aadhaar are needed (KYC/background verification), and give clear next steps.
- **Resilience:** wrap all LLM calls with timeout + error handling; if the API key is missing or the call fails, the app should degrade gracefully (e.g., status `failed`, visible error in the UI) rather than 500-crash the whole request.

### 4. Frontend Requirements

- **Upload page:** drag-and-drop resume upload with a visible progress indicator during upload + parsing
- **Dashboard:** table of all candidates — name, email, company, extraction status (color-coded badges: processing/parsed/failed/documents_submitted)
- **Candidate profile view:** parsed fields displayed with their confidence scores (e.g., a small percentage or color bar next to each field), a "Request Documents" button, and a panel showing the generated request message once triggered
- **Document section:** upload UI for PAN/Aadhaar with file previews, and a submitted/pending state
- Use clean, modern styling (Tailwind is fine) — this doesn't need to be fancy, but should look intentional, not unstyled HTML

### 5. Non-functional requirements
- `.env.example` listing every required environment variable (API keys, DB URL, etc.) — never hardcode secrets
- Input validation and sensible HTTP status codes on every endpoint
- CORS configured correctly for local dev (frontend on a different port than backend)
- Seed script or sample resume(s) in `/samples` so a grader can test immediately without sourcing their own file
- Basic tests for at least: resume upload → parse flow, and the document-request generation

### 6. Deliverables (must all be present at the end)
1. **Public GitHub repo** with clear commit history (not one giant commit) and a top-level `README.md` covering: architecture overview, setup instructions (backend + frontend), environment variables needed, and any assumptions/tradeoffs made given the time constraints
2. **Deployed instance** (Render/Railway/Vercel) — include the live URL in the README; if deployment isn't feasible in the time available, say so explicitly in the README along with exact local run instructions
3. A short **architecture diagram** (even a simple one) in the README showing: Resume Upload → Parsing Service → LLM → Structured Data → DB, and Document Request → Agent → Log
4. Leave a clear placeholder/checklist in the README for the **Loom walkthrough** (≤5 min) covering: architecture → upload resume → view extracted data → trigger document request — I will record this myself

### 7. Build order
Please build in this order and check in with a brief summary after each phase before moving to the next:
1. Backend skeleton + DB models + file upload endpoint (no AI yet, just storage)
2. LLM integration for resume parsing + confidence scoring
3. Remaining CRUD endpoints (`GET /candidates`, `GET /candidates/<id>`)
4. Document-request agent + logging
5. Document submission endpoint
6. React frontend wired to all of the above
7. README, seed samples, tests, deployment config

Start with Phase 1.

---

### Notes for you (not part of the AI prompt)
- **PAN/Aadhaar are sensitive Indian government ID types** — even for a test project, don't log real ones; use the sample data you generate yourself and mention in the README that this is a demo, not a production KYC system.
- Fill in `[Anthropic/OpenAI/OpenRouter API key source]` and your GitHub username before sending this to your coding assistant if you want it to also scaffold repo/deploy configs.
- If your assistant supports it, paste this whole prompt in one shot rather than splitting it — the "build order" section is designed to keep a single long session on track.
