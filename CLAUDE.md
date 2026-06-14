# IELTS Anywhere — Backend Codebase Guide

## Project Overview

FastAPI backend for an IELTS practice platform. Handles 4 test modules: **Listening**, **Reading**, **Writing**, **Speaking**. Two subscription tiers: **Free** (Listening + Reading + Diagnostic) and **Pro** (Writing, Speaking, Grammar, Vocabulary, full mock tests, analytics).

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.135 + Uvicorn (async) |
| Database | PostgreSQL (Supabase) via SQLAlchemy 2.0 + asyncpg |
| Migrations | Alembic |
| Task Queue | Celery 5.6 + Redis (Upstash) |
| Auth | Firebase Admin SDK (JWT verification) |
| LLM | Anthropic Claude Haiku (`claude-haiku-4-5-20251001`) + Sonnet (`claude-sonnet-4-6`) |
| Storage | Cloudflare R2 (S3-compatible, via boto3) |
| Payments | LemonSqueezy (webhook + checkout) |
| Email | Resend |
| Voice | ElevenLabs Conversational Agent + OpenAI Whisper (transcription) |

---

## Directory Layout

```
app/
  main.py          # FastAPI app, CORS, lifespan, router registration
  api/routes/      # One file per domain (11 routers)
  core/
    config.py      # Settings (pydantic-settings, env vars)
    security.py    # Firebase Admin init + JWT verification
  models/          # SQLAlchemy ORM models
  schemas/         # Pydantic request/response schemas
  services/        # Business logic (grading, scoring, storage, email)
  tasks/           # Celery task definitions
  db/
    session.py     # AsyncSessionLocal factory
    base.py        # Declarative base
    seed*.py       # Data seeding scripts
alembic/           # 11 migration files
scripts/           # One-off migration helper scripts
Dockerfile         # API server
Dockerfile.celery  # Celery worker
requirements.txt   # Python dependencies
```

---

## Authentication

All protected routes use:
```python
current_user: User = Depends(get_current_user)  # from app/core/security.py
```

Flow:
1. Client sends `Authorization: Bearer <firebase_jwt>`
2. `get_current_user()` verifies JWT with Firebase Admin SDK
3. Looks up user by `firebase_uid` in DB; creates on first login
4. Returns `User` ORM object

Admin routes additionally check `current_user.is_admin`.
Pro routes check `current_user.subscription == SubscriptionTier.pro`.

---

## Database Models (`app/models/`)

| Model | Table | Key fields |
|---|---|---|
| `User` | `users` | `firebase_uid`, `email`, `subscription` (free/pro), `is_admin` |
| `TestAttempt` | `test_attempts` | `module` (writing/speaking/reading/listening), `status`, `overall_band`, `improvement_tips` (JSON) |
| `IeltsTest` | `ielts_tests` | Links to listening/reading/writing/speaking test IDs |
| `TestSession` | `test_sessions` | Tracks user progress through a full IELTS test (per-module completion flags) |
| `WritingTest/Task` | `writing_tests/tasks` | 2 tasks per test |
| `SpeakingTest/Part` | `speaking_tests/parts` | 3 parts per test |
| `ListeningTest/Section/Subsection/Question` | 4 tables | 4-part hierarchy |
| `ReadingTest/Passage/QuestionGroup/Question` | 4 tables | 3-passage hierarchy |
| `SpeakingAttempt` | `speaking_attempts` | ElevenLabs results (JSONB transcript, per-criterion bands) |
| `Affiliate/AffiliateReferral` | `affiliates/affiliate_referrals` | Commission rates, referral tracking |

### Subscription Tiers
```python
class SubscriptionTier(str, Enum):
    free = "free"
    pro  = "pro"
```

---

## API Routes (88 total)

### Auth
- `GET /auth/me` — Get/create current user

### Sessions (`app/api/routes/sessions.py`)
- `GET /sessions/tests` — Available IELTS tests
- `POST /sessions/start` — Create or resume session
- `GET /sessions/{id}` — Session state
- `POST /sessions/{id}/start-module` — Begin module (starts timer)
- `POST /sessions/{id}/reset-module` — Reset current module
- `POST /sessions/{id}/complete-module` — Mark module done
- `POST /sessions/{id}/restart` — Reset entire session
- `GET /sessions/{id}/time-remaining`
- `GET /sessions/{id}/results` — Full results with tips
- `GET /sessions/tests/{test_id}/last-result` — Last score for a test

### Writing (`app/api/routes/writing.py`)
- `GET /writing/tests` — List writing tests
- `GET /writing/tests/{id}` — Test detail
- `GET /writing/for-session/{session_id}`
- `POST /writing/submit` — Queue Celery grading → returns `attempt_id`
- `GET /writing/attempts/{id}?lang=en|bn` — Poll status / get result
- `GET /writing/attempts` — User history

### Speaking (`app/api/routes/speaking.py`)
- `GET /speaking/for-session/{session_id}`
- `POST /speaking/submit` — Queue Celery grading
- `GET /speaking/attempts/{id}` — Poll grading status
- `POST /speaking/transcribe` — Upload audio → OpenAI Whisper → transcript
- `GET /speaking/el-signed-url` — ElevenLabs conversation URL
- `POST /speaking/el-submit` — Submit ElevenLabs transcript (Claude Sonnet grades)
- `GET /speaking/results/{attempt_id}` — ElevenLabs result
- `GET /speaking/history` — ElevenLabs history

### Reading (`app/api/routes/reading.py`)
- `GET /reading/tests`, `GET /reading/tests/{id}`
- `GET /reading/for-session/{session_id}`
- `POST /reading/submit` — Instant rule-based scoring
- `GET /reading/attempts`, `GET /reading/attempts/{id}`

### Listening (`app/api/routes/listening.py`)
- `GET /listening/tests`, `GET /listening/tests/{id}`
- `GET /listening/for-session/{session_id}`
- `POST /listening/submit` — Instant rule-based scoring
- `GET /listening/attempts`, `GET /listening/attempts/{id}?lang=en|bn`

### Dashboard (`app/api/routes/dashboard.py`)
- `GET /dashboard` — Stats, module avgs, weakness analysis, personalized tips

### Learn — Pro only (`app/api/routes/learn.py`)
- `POST /learn/vocabulary` — Claude-generated vocab exercises
- `POST /learn/grammar` — Claude-generated grammar exercises

### Payments (`app/api/routes/payments.py`)
- `GET /payments/checkout-url` — LemonSqueezy checkout link
- `POST /payments/webhook` — LemonSqueezy events (upgrades user to Pro on order)

### Affiliates (`app/api/routes/affiliates.py`)
- `GET /affiliate/me`, `GET /affiliate/validate/{code}`

### Admin (`app/api/routes/admin.py`) — 40+ endpoints
- User management: list, override subscription, toggle admin flag
- CRUD for all test types (listening, reading, writing, speaking, IELTS shells)
- Audio upload to R2
- Batch question tip generation
- Affiliate management
- Pricing + time limit config

---

## Grading Architecture

### MCQ modules (instant, synchronous)
**Reading** and **Listening** submit routes score immediately:
- `reading_scorer.py` / `listening_scorer.py` — rule-based answer matching
- Band mapped from % correct (raw score → band lookup table)
- Optional: LLM-generated `wrong_answer_tip` per question (pre-generated by admin)
- Async Celery task queued after submit to optionally upgrade tips with LLM feedback

### AI-graded modules (async, Celery)
**Writing** and **Speaking** queue Celery tasks on submit, frontend polls for result:

```
POST /writing/submit
  → creates TestAttempt (status="grading")
  → grade_writing_task.delay(attempt_id)

GET /writing/attempts/{id}   ← frontend polls
  → returns status field: "grading" | "graded" | "error"
```

**Writing grader** (`services/writing_grader.py`):
- Model: `claude-haiku-4-5-20251001`
- 4 criteria per task: `task_achievement`, `coherence_cohesion`, `lexical_resource`, `grammatical_range`
- Returns band scores (0.5 increments, 1.0–9.0), feedback, highlighted error examples

**Speaking grader** (`services/speaking_grader.py`):
- Same model; 4 criteria per part: `fluency_coherence`, `lexical_resource`, `grammatical_range`, `pronunciation`
- ElevenLabs variant uses `claude-sonnet-4-6` and grades in `speaking/el-submit`

### Bengali translation (`?lang=bn`)
- `GET /listening/attempts/{id}?lang=bn` and `GET /writing/attempts/{id}?lang=bn`
- Backend translates `improvement_tips` to Bengali via Claude before returning
- All other fields always returned in English

---

## Celery Tasks (`app/tasks/grading.py`)

| Task | Trigger | Description |
|---|---|---|
| `grade_writing_task` | Writing submit | Claude grades 2 tasks, updates TestAttempt |
| `grade_speaking_task` | Speaking submit | Claude grades 3 parts, updates TestAttempt |
| `generate_feedback_task` | Reading/Listening submit | LLM upgrades rule-based tips (gated) |
| `generate_question_tips_task` | Admin action | Pre-generates `wrong_answer_tip` for all questions |
| `_notify_module_graded` | After grading | Sends completion email via Resend |

Retry policy: `max_retries=3`, 10s countdown between retries.

Celery runs in a **separate container** (`Dockerfile.celery`).

---

## Key Services

| Service | File | Purpose |
|---|---|---|
| Writing Grader | `services/writing_grader.py` | Claude grading for writing submissions |
| Speaking Grader | `services/speaking_grader.py` | Claude grading for speaking submissions |
| Listening Scorer | `services/listening_scorer.py` | Rule-based MCQ scoring + band calculation |
| Reading Scorer | `services/reading_scorer.py` | Rule-based MCQ scoring + per-question feedback |
| Feedback Generator | `services/feedback_generator.py` | Claude-generated tips for reading/listening |
| Feedback Gating | `services/feedback_gating.py` | Throttles LLM calls (first attempt, band delta ≥ 0.5, or 5+ attempts) |
| Question Tips | `services/question_tips_generator.py` | Pre-generates `wrong_answer_tip` per question |
| Storage | `services/storage.py` | Cloudflare R2 upload/delete via boto3 |
| Email | `services/email.py` | Resend email delivery |

---

## Environment Variables

```bash
# Required
DATABASE_URL=postgresql+asyncpg://...
ANTHROPIC_API_KEY=sk-ant-...
REDIS_URL=rediss://...
FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/service-account.json
# or: FIREBASE_SERVICE_ACCOUNT_B64=<base64-encoded JSON>

# Payments
LEMONSQUEEZY_API_KEY=
LEMONSQUEEZY_WEBHOOK_SECRET=
LEMONSQUEEZY_PRO_VARIANT_ID=

# Storage
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_PUBLIC_URL=

# Voice
OPENAI_API_KEY=          # Whisper transcription
ELEVENLABS_API_KEY=
ELEVENLABS_AGENT_ID=

# Email
RESEND_API_KEY=
FROM_EMAIL=noreply@ieltsanywhere.app

# Module time limits (seconds, with defaults)
LISTENING_TIME_LIMIT=1800
READING_TIME_LIMIT=3600
WRITING_TIME_LIMIT=3600
SPEAKING_TIME_LIMIT=900
```

---

## Development Conventions

- **Async everywhere** — all DB operations use `async with AsyncSession`, all routes are `async def`
- **Dependency injection** — DB session via `get_db()` Depends, user via `get_current_user()` Depends
- **Schema separation** — Pydantic schemas in `app/schemas/` separate from SQLAlchemy models in `app/models/`
- **Claude model defaults** — Haiku for grading/generation, Sonnet only for ElevenLabs speaking (higher quality)
- **Prompt caching** — Use `"cache_control": {"type": "ephemeral"}` on long system prompts
- **Migrations** — Always use Alembic (`alembic revision --autogenerate -m "..."` + `alembic upgrade head`)
- **Audio storage** — Always go through `services/storage.py`; files stored as `audio/<uuid>.<ext>`
- **Error handling** — Routes return `HTTPException` with clear status codes; services raise plain `Exception` which tasks catch and store as `status="error"` on the attempt

---

## Running Locally

```bash
# API server
uvicorn app.main:app --reload --port 8000

# Celery worker (separate terminal)
celery -A app.tasks.grading worker --loglevel=info

# Database migrations
alembic upgrade head
```
