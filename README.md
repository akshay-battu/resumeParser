# ResumeParser

Upload a candidate's resume, extract structured profile data with an LLM, and automatically request — then collect — their PAN and Aadhaar identity documents by email.

## Live deployment

**https://resumeparser-production-f5cd.up.railway.app**

Deployed on Railway, built from this repo's `Dockerfile` — same container image as local Docker Compose, just with `DATABASE_URL`/`UPLOAD_FOLDER` pointed at a persistent volume mounted at `/data` (Railway's filesystem is otherwise ephemeral) and `CORS_ORIGINS` set to the deployed domain. Pushing to `main` auto-redeploys via the connected GitHub repo.

## Quick start (Docker Compose)

**Prerequisites:** Docker Desktop, a [Gemini API key](https://aistudio.google.com/), and a mailbox with SMTP + IMAP access (e.g. Gmail with an [App Password](https://myaccount.google.com/apppasswords)).

```bash
cp .env.example .env
# then edit .env — see "Environment variables" below
docker-compose up --build
```

Open **http://localhost:5000** — that's the whole app (API + UI in one container).

Stop it with `docker-compose down` (add `-v` only if you also want to wipe the named volumes — there aren't any by default, since uploads/DB persist to `backend/` on your host).

### Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Notes |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Powers resume parsing, message drafting, attachment classification |
| `SENDGRID_API_KEY` / `SENDGRID_FROM` | For real email on hosts that block SMTP | Sends via [SendGrid](https://sendgrid.com)'s HTTPS API instead — takes priority over SMTP when set. Needed on Railway's free/trial tier, which blocks outbound SMTP entirely. `SENDGRID_FROM` must be verified via SendGrid's Single Sender flow (no domain/DNS needed) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | For real email | Gmail: `smtp.gmail.com`, `587`, your address, an App Password, your address |
| `SMTP_FROM_NAME` | No | Display name shown to candidates (default: "ResumeParser Recruiting") — the address itself can't differ from `SMTP_FROM`, since replies route back to it |
| `IMAP_HOST` / `IMAP_PORT` / `IMAP_USER` / `IMAP_PASSWORD` | For auto-attach | Same mailbox as SMTP — Gmail: `imap.gmail.com`, `993` |
| `IMAP_AUTO_POLL` / `IMAP_POLL_INTERVAL_SECONDS` | No | Background inbox polling, on by default every 300s |

If SMTP/IMAP are left blank, the app still works — document requests get logged instead of sent, and inbox sync reports "not configured."

## What it does

1. **Upload** a resume (PDF/DOCX) → text extracted → sent to Gemini → structured fields (name, email, company, skills, …) with confidence scores, stored per candidate.
2. **Generate** a personalized PAN/Aadhaar request message (LLM-drafted), review/edit it, then **send** it by email.
3. **Candidate replies** with attachments → a background poller (or the manual "Sync Email Inbox" button) reads the inbox, classifies attachments via LLM, and auto-attaches them to the right candidate — no manual upload needed. Manual upload is also available as a fallback. Every request email sets an invisible Reply-To (a plus-addressed variant of the sending mailbox, e.g. `hr+rp7@gmail.com`), so replies match back to the exact candidate row even if two candidates share the same email address — nothing is appended to the visible subject/body.
4. **View** submitted documents (image/PDF preview + download) on the candidate's profile.
5. **Edit** any auto-extracted field if the parser got something wrong — corrected fields are marked as fully confident.
6. **Delete** a candidate to permanently remove their resume, documents, and request history.
7. **Gemini quota/rate-limit errors** (HTTP 429) surface as a dismissible alert banner across the UI, not a silent failure or a raw stack trace — see `LLMQuotaExceededError` in `backend/app/services/llm/base.py` and `ToastContext` in `frontend/src/context/`.

## Architecture

Everything runs in one Flask process: the API, the LLM calls, and a daemon thread that polls the mailbox on an interval. The React app is built once and served as static files by the same Flask app — there's no separate frontend server in production.

### Data flow

```mermaid
flowchart TD
    A([HR uploads resume]) --> B["POST /candidates/upload"]
    B --> C[LocalStorageService saves file to disk]
    C --> D[resume_extractor: PDF/DOCX to raw text]
    D --> E{Gemini: parse_resume_text}
    E -->|success| F[(Candidate row: fields + confidence)]
    E -->|429 / quota exceeded| G["status=failed, error_type=quota_exceeded"]
    G --> H[["UI alert: quota exceeded"]]
    F --> I([HR clicks Generate Message])
    I --> J["POST /generate-document-request"]
    J --> K{Gemini: draft message}
    K -->|success| L[HR reviews / edits in browser]
    K -->|429 / quota exceeded| H
    L --> M([HR clicks Send Email])
    M --> N["POST /request-documents"]
    N --> O[NotificationService: SendGrid or SMTP]
    O --> P[(DocumentRequest row)]
    O --> Q([Candidate's inbox])
    Q --> R([Candidate replies with PAN/Aadhaar])
    R --> S[Background poller or Sync button: IMAP fetch]
    S --> T{Gemini: classify attachments}
    T --> U[LocalStorageService saves PAN/Aadhaar]
    U --> F
    F --> V([HR views documents on profile])
```

### High-level design

```mermaid
flowchart LR
    subgraph Client [Browser]
        UI["React SPA — Upload / Dashboard / Profile"]
    end

    subgraph Server ["Single Flask process (gunicorn)"]
        Routes["candidates routes — REST JSON API"]
        Services["Service layer — parsing, drafting,\nnotification, ingestion"]
        Poller["Background thread — IMAP poller, every 300s"]
    end

    subgraph External ["Third-party services"]
        Gemini[("Google Gemini, via LangChain")]
        Mail[("SMTP / SendGrid / IMAP mailbox")]
    end

    subgraph Persistence
        DB[(SQLite)]
        Files[("Local filesystem /\npersistent volume")]
    end

    UI <-->|HTTPS JSON| Routes
    Routes --> Services
    Poller --> Services
    Services --> Gemini
    Services --> Mail
    Services --> DB
    Services --> Files
```

### Interfaces

The service layer is built against abstract interfaces, not concrete providers — swapping Gemini, SendGrid, or local disk storage for something else means adding a class, not touching business logic.

```mermaid
classDiagram
    class LLMClient {
        <<interface>>
        +complete_json(prompt, schema_hint, timeout) dict
    }
    class LangChainGeminiClient
    LLMClient <|.. LangChainGeminiClient

    class NotificationService {
        <<interface>>
        +send(channel, recipient, message, subject, candidate_id) SendResult
    }
    class StubNotificationService
    class SMTPNotificationService
    class SendGridNotificationService
    NotificationService <|.. StubNotificationService
    NotificationService <|.. SMTPNotificationService
    NotificationService <|.. SendGridNotificationService
    NotificationService ..> SendResult

    class StorageService {
        <<interface>>
        +save(file, subfolder) str
    }
    class LocalStorageService
    StorageService <|.. LocalStorageService

    class SendResult {
        +bool success
        +str status
        +str detail
    }
```

## Project structure

```
backend/app/
  models/        Candidate, DocumentRequest (SQLAlchemy)
  routes/        candidates.py — all API endpoints
  services/      resume parsing, LLM client, document request drafting,
                 SMTP send, IMAP ingest + classification, local file storage
backend/tests/   Pytest suite
backend/scripts/ copy_frontend.py, generate_sample_resume.py
frontend/src/    pages/ (Upload, Dashboard, CandidateProfile), components/
samples/         Sample resume for testing the upload flow
```

## Tests

```bash
cd backend
pytest -q
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/candidates/upload` | Upload resume (PDF/DOCX) |
| GET | `/candidates` | List candidates (`?status=` filter) |
| GET | `/candidates/<id>` | Full profile + confidence + document metadata |
| PATCH | `/candidates/<id>` | Correct auto-extracted fields (name/email/phone/company/designation/skills) |
| DELETE | `/candidates/<id>` | Permanently delete candidate, files, and request history |
| GET | `/candidates/<id>/documents/<type>` | Serve a file (`pan` / `aadhaar` / `resume`) |
| POST | `/candidates/<id>/generate-document-request` | Draft a request message (not sent) |
| POST | `/candidates/<id>/request-documents` | Send a (reviewed/edited) request message |
| POST | `/candidates/<id>/submit-documents` | Upload PAN/Aadhaar manually |
| POST | `/candidates/sync-inbox` | Manually trigger an inbox check |
| GET | `/health` | Health check |

## License

MIT
