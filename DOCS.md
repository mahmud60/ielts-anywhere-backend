# IELTS Anywhere — Backend Developer Reference

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Environment Variables](#2-environment-variables)
3. [Database Models](#3-database-models)
4. [API Endpoints](#4-api-endpoints)
5. [Request & Response Schemas](#5-request--response-schemas)
6. [Scoring & Grading Logic](#6-scoring--grading-logic)
7. [Celery Task Queue](#7-celery-task-queue)
8. [Speaking Agent](#8-speaking-agent)
9. [Services Reference](#9-services-reference)
10. [Auth Flow](#10-auth-flow)
11. [Session Flow](#11-session-flow)
12. [Running Locally](#12-running-locally)
13. [CI/CD Pipeline](#13-cicd-pipeline)

---

## 1. Architecture Overview

```
Next.js Frontend (Vercel)
         │
         │  HTTPS / Bearer token (Firebase JWT)
         ▼
┌─────────────────────────────────────────────────────────┐
│  FastAPI  (Google Cloud Run — auto-scales 1-10)         │
│   app/main.py — CORS, exception handler, lifespan       │
│   app/api/routes/*.py — all endpoints                   │
└──────────┬──────────────────────┬───────────────────────┘
           │                      │
           │ asyncpg              │ Celery tasks (fire-and-forget)
           ▼                      ▼
    PostgreSQL (Supabase)    Redis (broker + result backend)
                                  │
                                  ▼
                         ┌────────────────────┐
                         │  Celery Worker VM  │
                         │  (GCP e2-small)    │
                         │  grade_writing_task│
                         │  grade_speaking_task│
                         │  generate_*_task   │
                         └────────────────────┘

    LiveKit Cloud ◄──── Speaking Agent VM (GCP e2-small) ────► OpenAI TTS
                              speaking_agent.py               Deepgram STT
                                                              GPT-4o-mini LLM

External Services:
  Anthropic Claude  — writing grading (Haiku), speaking scoring (Sonnet)
  Cloudflare R2     — audio file storage (boto3 S3-compatible)
  LemonSqueezy      — Pro subscriptions + affiliate commissions
  Firebase Admin    — JWT verification + user identity
  Resend            — transactional email
```

### Tech Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI 0.135.3 (async, ASGI) |
| ORM | SQLAlchemy 2.0 (async mode, asyncpg driver) |
| Database | PostgreSQL (Supabase) |
| Task queue | Celery 5.6.3 + Redis |
| AI grading | Anthropic Claude Haiku (writing/speaking/tips) + Sonnet (speaking session) |
| Speaking pipeline | LiveKit WebRTC + Deepgram STT + GPT-4o-mini + OpenAI TTS |
| Storage | Cloudflare R2 (audio files) |
| Auth | Firebase Admin SDK (JWT verification) |
| Payments | LemonSqueezy (webhooks + checkout) |
| Email | Resend |
| Migrations | Alembic |
| Container | Docker → Google Artifact Registry → Cloud Run |

---

## 2. Environment Variables

All settings live in `app/core/config.py` as a Pydantic `BaseSettings` class.

### Core

| Variable | Type | Default | Description |
|---|---|---|---|
| `APP_NAME` | `str` | `"IELTS ANYWHERE"` | App title |
| `DEBUG` | `bool` | `False` | SQLAlchemy echo + verbose errors |
| `DATABASE_URL` | `str` | — | `postgresql+asyncpg://user:pass@host/db?ssl=require` |
| `REDIS_URL` | `str` | — | `redis://...` or `rediss://...` for TLS |
| `ANTHROPIC_API_KEY` | `str` | — | Claude API key |

### Firebase Auth

| Variable | Type | Default | Description |
|---|---|---|---|
| `FIREBASE_SERVICE_ACCOUNT_PATH` | `str` | `firebase-service-account.json` | Path to service account JSON (local dev) |
| `FIREBASE_SERVICE_ACCOUNT_B64` | `str` | `""` | Base64-encoded JSON (production — takes precedence) |

### LemonSqueezy (Payments)

| Variable | Type | Default | Description |
|---|---|---|---|
| `LEMONSQUEEZY_API_KEY` | `str` | `""` | API key for checkout URL generation |
| `LEMONSQUEEZY_WEBHOOK_SECRET` | `str` | `""` | HMAC-SHA256 webhook signing secret |
| `LEMONSQUEEZY_PRO_VARIANT_ID` | `str` | `""` | UUID of the Pro plan variant |

### Cloudflare R2 (Storage)

| Variable | Type | Default | Description |
|---|---|---|---|
| `R2_ACCOUNT_ID` | `str` | `""` | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | `str` | `""` | R2 access key |
| `R2_SECRET_ACCESS_KEY` | `str` | `""` | R2 secret key |
| `R2_BUCKET_NAME` | `str` | `""` | Target bucket name |
| `R2_PUBLIC_URL` | `str` | `""` | Public URL prefix (e.g. `https://pub-xxx.r2.dev`) |

### Speaking Agent

| Variable | Type | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | `str` | `""` | OpenAI TTS + GPT-4o-mini (speaking agent) |
| `LIVEKIT_API_KEY` | `str` | `""` | LiveKit API key |
| `LIVEKIT_API_SECRET` | `str` | `""` | LiveKit API secret |
| `LIVEKIT_URL` | `str` | `""` | `wss://your-app.livekit.cloud` |
| `DEEPGRAM_API_KEY` | `str` | `""` | Deepgram Nova-2 STT |
| `GOOGLE_API_KEY` | `str` | `""` | Google Gemini (fallback LLM — currently using OpenAI) |

### Email

| Variable | Type | Default | Description |
|---|---|---|---|
| `RESEND_API_KEY` | `str` | `""` | Resend API key (omit to stub-mode to stdout) |
| `FROM_EMAIL` | `str` | `"noreply@ieltsanywhere.app"` | Sender address |

### Analytics (PostHog)

| Variable | Type | Default | Description |
|---|---|---|---|
| `POSTHOG_API_KEY` | `str` | `""` | PostHog Project API Key. Blank disables server-side events (no-op). Same key the frontend uses. |
| `POSTHOG_HOST` | `str` | `"https://us.i.posthog.com"` | PostHog ingestion host (`us` or `eu`). |

Server-side events are sent from `app/services/analytics.py` (keyed by Firebase UID to stitch with the frontend's identified person): `subscription_activated`, `subscription_cancelled`, `referral_converted` — all fired from the LemonSqueezy webhook.

### Time Limits

| Variable | Type | Default | Equivalent |
|---|---|---|---|
| `LISTENING_TIME_LIMIT` | `int` | `1800` | 30 min |
| `READING_TIME_LIMIT` | `int` | `3600` | 60 min |
| `WRITING_TIME_LIMIT` | `int` | `3600` | 60 min |
| `SPEAKING_TIME_LIMIT` | `int` | `900` | 15 min |

---

## 3. Database Models

### 3.1 User (`app/models/user.py`)

```python
class SubscriptionTier(str, enum.Enum):
    free = "free"
    pro  = "pro"

class User(Base):
    __tablename__ = "users"
    id                       : UUID         # PK, default uuid4
    firebase_uid             : str          # unique, indexed
    email                    : str          # unique, indexed
    full_name                : str | None
    is_active                : bool         # default True
    is_admin                 : bool         # default False
    subscription             : SubscriptionTier  # default free
    lemonsqueezy_customer_id : str | None   # unique
    feedback_state           : JSON | None  # {module: {last_band, last_attempt_id, last_attempt_number}}

    # Relationships
    test_attempts : list[TestAttempt]
    sessions      : list[TestSession]
    affiliate     : Affiliate | None        # one-to-one
```

### 3.2 TestAttempt (`app/models/test.py`)

Stores the result of a single module attempt (listening, reading, writing, or speaking).

```python
class ModuleType(str, enum.Enum):
    listening = "listening"
    reading   = "reading"
    writing   = "writing"
    speaking  = "speaking"

class GradingStatus(str, enum.Enum):
    pending  = "pending"
    grading  = "grading"
    complete = "complete"
    failed   = "failed"

class TestAttempt(Base):
    __tablename__ = "test_attempts"
    id                : UUID
    user_id           : UUID           # FK → users.id
    module            : ModuleType
    status            : GradingStatus  # default pending
    overall_band      : float | None   # e.g. 6.5
    subscores         : JSON | None    # module-specific breakdown (see Grading section)
    ai_feedback       : str | None     # prose summary from Claude
    improvement_tips  : JSON | None    # list[str] of 3-5 tips
    raw_answers       : JSON | None    # student's submitted answers, preserved for audit
    test_id           : str | None     # references the test template UUID
    question_results  : JSON | None    # per-question scoring data
```

**`subscores` shape by module:**
- **Listening/Reading:** `{section_scores: {part: {correct, total, band}}, correct, total}`
- **Writing:** `{task1: {task_achievement, coherence_cohesion, lexical_resource, grammatical_range, band, feedback, word_count, raw_text, errors: {...}}, task2: {...}}`
- **Speaking:** `{part1: {fluency_coherence, lexical_resource, grammatical_range, pronunciation, band, feedback}, part2: {...}, part3: {...}}`

### 3.3 IeltsTest (`app/models/ielts_test.py`)

A test shell that links one of each module test together into a full IELTS test.

```python
class IeltsTest(Base):
    __tablename__ = "ielts_tests"
    id                 : UUID
    title              : str
    test_type          : str        # "academic" or "general", default "academic"
    is_active          : bool       # default True
    is_demo            : bool       # default False — free-tier tests only

    # FK links to individual module tests (any can be null)
    listening_test_id  : UUID | None  # FK → listening_tests.id
    reading_test_id    : UUID | None  # FK → reading_tests.id
    writing_test_id    : UUID | None  # FK → writing_tests.id
    speaking_test_id   : UUID | None  # FK → speaking_tests.id

    sessions           : list[TestSession]
```

### 3.4 TestSession (`app/models/ielts_test.py`)

One student's attempt at a full IELTS test (tracks progress across all 4 modules).

```python
class SessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed   = "completed"

class TestSession(Base):
    __tablename__ = "test_sessions"
    id                    : UUID
    user_id               : UUID         # FK → users.id
    ielts_test_id         : UUID         # FK → ielts_tests.id
    status                : SessionStatus  # default in_progress

    # Set once the module attempt is submitted
    listening_attempt_id  : UUID | None
    reading_attempt_id    : UUID | None
    writing_attempt_id    : UUID | None
    speaking_attempt_id   : UUID | None

    module_bands          : JSON  # {listening: 6.5, reading: null, ...}
    module_started_at     : JSON  # {listening: "2024-01-01T10:00:00Z", ...}
    completed_at          : datetime | None
    last_activity_at      : datetime | None
```

### 3.5 Listening Models (`app/models/listening.py`)

```python
class ListeningTest(Base):
    __tablename__ = "listening_tests"
    id                : UUID
    title             : str
    description       : str | None
    task              : str       # default "ielts_listening"
    type              : str       # default "text"
    test_order        : int | None
    is_active         : bool      # default True
    is_recommended    : bool      # default False
    mock_test_order   : int | None
    sections          : list[ListeningSection]  # ordered by part

class ListeningSection(Base):
    __tablename__ = "listening_sections"
    id          : int     # auto-increment PK
    test_id     : UUID    # FK → listening_tests.id
    part        : int     # 1–4
    title       : str | None
    audio       : str | None    # URL to audio file on R2
    transcript  : str | None
    subsections : list[ListeningSubsection]  # ordered by order

class ListeningSubsection(Base):
    __tablename__ = "listening_subsections"
    id               : int
    section_id       : int       # FK → listening_sections.id
    order            : int
    title            : str | None
    subsection_type  : str       # "form_completion", "mcq", "table", "matching", etc.
    instruction      : str | None
    visual           : str | None    # image/diagram URL
    grid_headers     : JSON | None
    grid_cells       : JSON | None
    questions        : list[ListeningQuestion]  # ordered by order

class ListeningQuestion(Base):
    __tablename__ = "listening_questions"
    id                    : int
    subsection_id         : int
    order                 : int
    group_label           : str | None   # e.g. "Question 1"
    question_type         : str          # "fill_in_the_blank", "multiple_choices", "multiple_select", "dropdown"
    ielts_question_type   : str | None
    stem                  : str | None   # the question text
    max_selected_options  : int | None   # for multiple_select
    options               : JSON         # [{"order": 1, "option": "text"}, ...]
    answer_key            : JSON         # varies by type (see scoring section)
    explanation           : str | None
    wrong_answer_tip      : str | None   # AI-generated (shown to Pro users)
```

### 3.6 Reading Models (`app/models/reading.py`)

```python
class ReadingQuestionType(str, enum.Enum):
    mcq                = "mcq"
    tfng               = "tfng"               # True / False / Not Given
    fill               = "fill"               # sentence/summary completion
    matching_headings  = "matching_headings"
    matching_info      = "matching_info"      # match to paragraph A/B/C
    short_answer       = "short_answer"
    multiple_select    = "multiple_select"

class ReadingTest(Base):
    __tablename__ = "reading_tests"
    id              : UUID
    title           : str
    description     : str | None
    test_type       : str     # "academic" or "general", default "academic"
    is_active       : bool
    is_demo         : bool
    is_recommended  : bool
    mock_test_order : int | None
    passages        : list[ReadingPassage]  # ordered by passage_number

class ReadingPassage(Base):
    __tablename__ = "reading_passages"
    id              : UUID
    test_id         : UUID
    passage_number  : int   # 1–3
    title           : str
    body            : str   # full prose text
    paragraphs      : JSON | None  # list[{"label": "A", "text": "..."}] for labelled paragraphs
    question_groups : list[ReadingQuestionGroup]  # ordered by order_index

class ReadingQuestionGroup(Base):
    __tablename__ = "reading_question_groups"
    id               : UUID
    passage_id       : UUID
    order_index      : int
    question_type    : ReadingQuestionType
    instruction      : str
    heading_options  : JSON | None   # list[str] for matching_headings
    paragraph_labels : JSON | None   # list[str] for matching_info (["A","B","C"])
    word_limit       : str | None    # e.g. "NO MORE THAN TWO WORDS"
    subsection_type  : str | None    # "regular", "form", "table", "flowchart"
    title            : str | None
    image            : str | None    # URL
    questions        : list[ReadingQuestion]  # ordered by order_index

class ReadingQuestion(Base):
    __tablename__ = "reading_questions"
    id               : UUID
    group_id         : UUID
    order_index      : int
    question_text    : str
    options          : JSON | None   # list[str] or dict
    answer_key       : JSON          # see answer_key formats below
    wrong_answer_tip : str | None    # AI-generated (Pro only)
    group_label      : str | None
    ielts_question_type : str | None
    max_selected_options : int | None
```

**`answer_key` formats by question type:**

| Type | Format | Example |
|---|---|---|
| `mcq` | `int` (option index) or `list[str]` (accepted text) | `0` or `["option A text"]` |
| `tfng` | `list[str]` | `["TRUE"]` / `["FALSE"]` / `["NOT GIVEN"]` |
| `fill` | `list[str]` (lowercase accepted answers) | `["temperature", "heat"]` |
| `matching_headings` | `str` (roman numeral) | `"iii"` |
| `matching_info` | `str` (paragraph letter) | `"B"` |
| `short_answer` | `list[str]` | `["two years", "2 years"]` |
| `multiple_select` | `list[str]` | `["A", "C"]` |

### 3.7 Writing Models (`app/models/writing.py`)

```python
class WritingTaskType(str, enum.Enum):
    task1_academic = "task1_academic"   # graph / chart / diagram description
    task1_general  = "task1_general"    # letter
    task2          = "task2"            # discursive essay

class WritingTest(Base):
    __tablename__ = "writing_tests"
    id          : UUID
    title       : str
    test_type   : str    # "academic" or "general"
    is_active   : bool
    is_demo     : bool
    tasks       : list[WritingTask]  # ordered by task_number

class WritingTask(Base):
    __tablename__ = "writing_tasks"
    id           : UUID
    test_id      : UUID
    task_number  : int            # 1 or 2
    task_type    : WritingTaskType
    prompt       : str            # the question/instruction shown to student
    stimulus     : str | None     # graph/chart description (Task 1)
    min_words    : int            # 150 (Task 1) or 250 (Task 2)
```

### 3.8 Speaking Models (`app/models/speaking.py`)

```python
class SpeakingPartType(str, enum.Enum):
    part1 = "part1"   # Interview — 4-5 questions (4-5 min)
    part2 = "part2"   # Long turn — cue card (3-4 min)
    part3 = "part3"   # Discussion — abstract questions (4-5 min)

class SpeakingTest(Base):
    __tablename__ = "speaking_tests"
    id        : UUID
    title     : str
    is_active : bool
    is_demo   : bool
    parts     : list[SpeakingPart]  # ordered by part_number

class SpeakingPart(Base):
    __tablename__ = "speaking_parts"
    id                     : UUID
    test_id                : UUID
    part_number            : int   # 1, 2, or 3
    part_type              : SpeakingPartType
    instructions           : str          # shown to student before speaking
    questions              : JSON         # list[str]
    cue_card               : str | None   # Part 2 only
    prep_time_seconds      : int          # Part 2 = 60, others = 0
    response_time_seconds  : int | None
```

### 3.9 SpeakingAttempt (`app/models/speaking_attempt.py`)

Used by the LiveKit speaking pipeline (separate from the legacy `TestAttempt.module=speaking`).

```python
class SpeakingAttempt(Base):
    __tablename__ = "speaking_attempts"
    id                          : UUID
    user_id                     : str
    status                      : str        # "in_progress" | "completed" | "failed"
    transcript                  : JSONB      # list[{role, text, timestamp}]
    overall_band                : Decimal(2,1) | None
    fluency_coherence_band      : Decimal(2,1) | None
    fluency_coherence_feedback  : str | None
    lexical_resource_band       : Decimal(2,1) | None
    lexical_resource_feedback   : str | None
    grammatical_range_band      : Decimal(2,1) | None
    grammatical_range_feedback  : str | None
    pronunciation_band          : Decimal(2,1) | None
    pronunciation_feedback      : str | None
    examiner_summary            : str | None
    errors                      : JSONB | None  # {criterion: [{label, originalText, correctedText, note}]}
    elevenlabs_session_id       : str | None    # legacy field
    completed_at                : datetime | None
```

### 3.10 Affiliate Models (`app/models/affiliate.py`)

```python
class ReferralStatus(str, enum.Enum):
    pending   = "pending"
    confirmed = "confirmed"
    paid      = "paid"

class Affiliate(Base):
    __tablename__ = "affiliates"
    id               : UUID
    user_id          : UUID            # FK → users.id (unique)
    code             : str             # unique, e.g. "JOHN20"
    commission_rate  : Decimal(5,4)    # default 0.2000 (20%)
    is_active        : bool            # default True
    discount_code    : str | None      # LemonSqueezy discount code for referrals
    referrals        : list[AffiliateReferral]

class AffiliateReferral(Base):
    __tablename__ = "affiliate_referrals"
    id                : UUID
    affiliate_id      : UUID           # FK → affiliates.id
    referred_user_id  : UUID | None    # FK → users.id (set after signup)
    order_id          : str | None     # unique — LemonSqueezy order ID
    order_amount      : Decimal(10,2) | None
    commission_amount : Decimal(10,2) | None
    status            : ReferralStatus  # default pending
```

### 3.11 VocabularyWord (`app/models/vocabulary.py`)

Pre-seeded bank of IELTS vocabulary words.

```python
class VocabularyWord(Base):
    __tablename__ = "vocabulary_words"
    id               : int      # auto-increment PK
    word             : str      # unique, indexed (max 100)
    module           : str      # indexed — "writing", "reading", "listening", "speaking"
    topic            : str      # indexed — "environment", "technology", "society", etc.
    band             : str      # "6.0", "7.0", "8.0"
    part_of_speech   : str      # "noun", "verb", "adjective", etc.
    definition       : str | None
    example          : str | None
    mnemonic         : str | None
    collocations     : JSONB    # default []
```

---

## 4. API Endpoints

Authentication: all endpoints (except `/payments/webhook` and `GET /sessions/tests`) require a Firebase ID token as `Authorization: Bearer <token>`.

Pro-only endpoints return `403 Forbidden` for free-tier users.

### 4.1 Auth — `/auth`

| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/me` | Get current user profile. Auto-creates user on first login. |
| `POST` | `/auth/link-referral` | Link a referral code stored from signup URL `?ref=CODE`. |

### 4.2 Listening — `/listening`

| Method | Path | Description |
|---|---|---|
| `GET` | `/listening/tests` | List all active listening tests. |
| `GET` | `/listening/tests/{test_id}` | Full test with sections → subsections → questions. |
| `GET` | `/listening/for-session/{session_id}` | Get listening test linked to a session. |
| `POST` | `/listening/submit` | Submit answers, score immediately, return results. |
| `GET` | `/listening/attempts` | User's last 20 listening attempts. |
| `GET` | `/listening/attempts/{attempt_id}` | Detailed result for one attempt (with tips). Accepts `?lang=bn`. |

### 4.3 Reading — `/reading`

| Method | Path | Description |
|---|---|---|
| `GET` | `/reading/tests` | List active reading tests. |
| `GET` | `/reading/tests/{test_id}` | Full test with passages → question groups → questions. |
| `GET` | `/reading/for-session/{session_id}` | Get reading test linked to session. |
| `POST` | `/reading/submit` | Submit answers, score, return results. |
| `GET` | `/reading/attempts` | User's last 20 reading attempts. |
| `GET` | `/reading/attempts/{attempt_id}` | Detailed result. Accepts `?lang=bn`. |

### 4.4 Writing — `/writing`

| Method | Path | Pro | Description |
|---|---|---|---|
| `GET` | `/writing/tests` | | List active writing tests. |
| `GET` | `/writing/tests/{test_id}` | | Full test with tasks. |
| `GET` | `/writing/for-session/{session_id}` | | Get test linked to session. |
| `POST` | `/writing/submit` | Yes | Submit responses → returns `202 pending`. Grading is async via Celery. |
| `GET` | `/writing/attempts/{attempt_id}` | | Poll for grading result (`pending` → `complete`). Accepts `?lang=bn`. |
| `GET` | `/writing/attempts` | | User's writing attempts. |

### 4.5 Speaking — `/speaking`

| Method | Path | Pro | Description |
|---|---|---|---|
| `GET` | `/speaking/for-session/{session_id}` | | Speaking test for session. |
| `GET` | `/speaking/attempts/{attempt_id}` | | Attempt result. |
| `POST` | `/speaking/transcribe` | | Upload audio → transcribe via Deepgram (multipart form). |
| `GET` | `/speaking/attempts` | | User's speaking attempts. |
| `POST` | `/speaking/lk-token` | Yes | Get LiveKit room JWT + room name + WebSocket URL. |
| `POST` | `/speaking/submit` | Yes | Submit transcript → grade via Claude Sonnet → save SpeakingAttempt. |
| `GET` | `/speaking/results/{attempt_id}` | | Get detailed speaking results. |
| `GET` | `/speaking/history` | | Last 10 completed speaking attempts. |

### 4.6 Sessions — `/sessions`

| Method | Path | Description |
|---|---|---|
| `GET` | `/sessions/tests` | List active IELTS tests. **Public — no auth required.** |
| `POST` | `/sessions/start` | Create (or resume) a session for a test. Body: `{ielts_test_id}`. |
| `GET` | `/sessions/my` | User's last 20 sessions. |
| `GET` | `/sessions/{session_id}` | Session state + `current_module` + `time_limit_seconds`. |
| `POST` | `/sessions/{session_id}/start-module` | Mark module as started, record `module_started_at`. |
| `GET` | `/sessions/{session_id}/time-remaining` | Seconds remaining for current module. |
| `POST` | `/sessions/{session_id}/reset-module` | Clear module timer (allow retake). |
| `GET` | `/sessions/{session_id}/last-scores` | Previous scores on this test (shown on expired screen). |
| `GET` | `/sessions/tests/{test_id}/last-result` | Most recent session results for this test. |
| `POST` | `/sessions/{session_id}/complete-module` | Link completed attempt, advance `current_module`. |
| `POST` | `/sessions/{session_id}/restart` | Reset all attempts, restore session to in-progress. |
| `GET` | `/sessions/{session_id}/results` | Full results for a completed session. |

### 4.7 Dashboard — `/dashboard`

| Method | Path | Description |
|---|---|---|
| `GET` | `/dashboard` | User stats, recent sessions, score history. Accepts `?lang=bn`. |

### 4.8 Learn — `/learn`

All endpoints require Pro subscription.

| Method | Path | Description |
|---|---|---|
| `GET` | `/learn/vocabulary/words` | Paginated vocab bank. Query: `module`, `topic`, `limit`, `offset`. |
| `POST` | `/learn/vocabulary` | Generate 4 AI vocab exercises + 3 phrases. Body: `{lang: "en"\|"bn"}`. |
| `POST` | `/learn/grammar` | Generate 4 grammar exercises + 2 pattern cards. Body: `{lang: "en"\|"bn"}`. |

### 4.9 Payments — `/payments`

| Method | Path | Description |
|---|---|---|
| `GET` | `/payments/checkout-url` | Generate LemonSqueezy checkout URL. Query: `?ref=CODE` (optional). |
| `POST` | `/payments/webhook` | Receive LemonSqueezy signed webhooks. Handles `order_created`, `subscription_created/updated/cancelled`. |

### 4.10 Affiliate — `/affiliate`

| Method | Path | Description |
|---|---|---|
| `GET` | `/affiliate/me` | Affiliate's own dashboard (referrals, commissions). |
| `GET` | `/affiliate/validate/{code}` | Validate an affiliate code. **Public.** |

### 4.11 Admin — `/admin`

All endpoints require `user.is_admin = True`.

**User Management**

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/stats` | Total users, Pro users, total tests. |
| `GET` | `/admin/users` | Paginated user list. Query: `skip`, `limit`, `search`. |
| `PATCH` | `/admin/users/{user_id}/subscription` | Set user to `free` or `pro`. |
| `PATCH` | `/admin/users/{user_id}/admin` | Toggle admin status. |

**Listening Management**

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/listening/tests` | List all tests. |
| `POST` | `/admin/listening/tests` | Create test. |
| `PATCH` | `/admin/listening/tests/{test_id}` | Update test metadata. |
| `DELETE` | `/admin/listening/tests/{test_id}` | Delete test. |
| `POST` | `/admin/listening/tests/{test_id}/sections` | Create section. |
| `PATCH` | `/admin/listening/sections/{section_id}` | Update section. |
| `POST` | `/admin/listening/sections/{section_id}/audio` | Upload audio to R2 (multipart). |
| `GET` | `/admin/listening/sections/{section_id}/subsections` | List subsections. |
| `POST` | `/admin/listening/sections/{section_id}/subsections` | Create subsection. |
| `PATCH` | `/admin/listening/subsections/{subsection_id}` | Update subsection. |
| `DELETE` | `/admin/listening/subsections/{subsection_id}` | Delete subsection. |
| `GET` | `/admin/listening/subsections/{subsection_id}/questions` | List questions. |
| `POST` | `/admin/listening/subsections/{subsection_id}/questions` | Create question. |
| `PATCH` | `/admin/listening/questions/{question_id}` | Update question. |
| `DELETE` | `/admin/listening/questions/{question_id}` | Delete question. |
| `POST` | `/admin/listening/tests/{test_id}/generate-tips` | Queue AI tip generation for all questions. |

**Reading Management**

| Method | Path | Description |
|---|---|---|
| `GET/POST` | `/admin/reading/tests` | List / create reading tests. |
| `PATCH/DELETE` | `/admin/reading/tests/{test_id}` | Update / delete. |
| `POST` | `/admin/reading/tests/{test_id}/generate-tips` | Queue tip generation. |
| `POST/PATCH/DELETE` | `/admin/reading/tests/{test_id}/passages` | Manage passages. |
| `POST/PATCH/DELETE` | `/admin/reading/passages/{passage_id}/groups` | Manage question groups. |
| `GET/POST` | `/admin/reading/groups/{group_id}/questions` | Manage questions. |
| `PATCH/DELETE` | `/admin/reading/questions/{question_id}` | Update / delete question. |

**Writing Management**

| Method | Path | Description |
|---|---|---|
| `GET/POST` | `/admin/writing/tests` | List / create. |
| `POST` | `/admin/writing/tests/{test_id}/tasks` | Add task (task_number 1 or 2). |
| `PATCH` | `/admin/writing/tasks/{task_id}` | Update task. |

**Speaking Management**

| Method | Path | Description |
|---|---|---|
| `GET/POST` | `/admin/speaking/tests` | List / create. |
| `POST` | `/admin/speaking/tests/{test_id}/parts` | Add part (part_number 1–3). |
| `PATCH` | `/admin/speaking/parts/{part_id}` | Update part. |

**IELTS Test Management**

| Method | Path | Description |
|---|---|---|
| `GET/POST` | `/admin/ielts-tests` | List / create IELTS test shells. |
| `PATCH` | `/admin/ielts-tests/{test_id}` | Link/unlink module tests (set FK IDs). |
| `DELETE` | `/admin/ielts-tests/{test_id}` | Delete shell (not the module tests). |

**Affiliate Management**

| Method | Path | Description |
|---|---|---|
| `POST` | `/admin/affiliates` | Create affiliate account for a user. |
| `GET` | `/admin/affiliates` | List all affiliates. |
| `PATCH` | `/admin/affiliates/{affiliate_id}` | Update commission_rate, is_active, discount_code. |
| `GET` | `/admin/affiliates/{affiliate_id}/referrals` | Get affiliate's referral list. |

**Config**

| Method | Path | Description |
|---|---|---|
| `GET` | `/admin/pricing` | Pricing config (from env). |
| `GET` | `/admin/time-limits` | Module time limits in seconds. |

---

## 5. Request & Response Schemas

### Submit Listening

```python
# POST /listening/submit
class SubmitListeningRequest(BaseModel):
    test_id : UUID
    answers : dict[str, Any]   # {str(question_id): answer}

# Response
class ListeningResultOut(BaseModel):
    attempt_id      : UUID
    correct         : int
    total           : int
    overall_band    : float
    section_scores  : dict       # {part: {correct, total, band}}
    question_results: list[QuestionResult]
    improvement_tips: list[str]

class QuestionResult(BaseModel):
    question_id    : str
    question_type  : str
    text           : str
    user_answer    : Any
    correct_answer : Any
    is_correct     : bool
    tip            : str | None  # Pro-only
    has_tip        : bool
```

### Submit Reading

```python
# POST /reading/submit
class SubmitReadingRequest(BaseModel):
    test_id : UUID
    answers : dict[str, Any]

# Response
class ReadingResultOut(BaseModel):
    attempt_id      : UUID
    correct         : int
    total           : int
    overall_band    : float
    passage_results : list[PassageResult]  # {passage_number, passage_title, correct, total, band}
    question_results: list[QuestionResult]
    improvement_tips: list[str]
```

### Submit Writing

```python
# POST /writing/submit
class SubmitWritingRequest(BaseModel):
    test_id   : UUID
    responses : dict[str, str]   # {str(task_id): essay_text}

# Response (202 Accepted — grading is async)
class WritingResultOut(BaseModel):
    attempt_id     : UUID
    status         : str              # "pending" | "complete" | "failed"
    overall_band   : float | None
    task_scores    : list[TaskScore] | None
    improvement_tips: list[str] | None

class TaskScore(BaseModel):
    task_number        : int
    task_type          : str
    task_achievement   : float
    coherence_cohesion : float
    lexical_resource   : float
    grammatical_range  : float
    band               : float
    feedback           : str
    word_count         : int
    task_prompt        : str | None
    raw_text           : str | None
    errors             : dict | None  # {criterion: [{label, originalText, correctedText, note}]}
```

### Submit Speaking

```python
# POST /speaking/submit  (LiveKit transcript)
class _SubmitBody(BaseModel):
    transcript  : list[dict]   # [{role: "user"|"agent", text, timestamp}]
    room_name   : str

# Response
class SpeakingResultOut(BaseModel):
    attempt_id     : UUID
    status         : str
    overall_band   : float | None
    fluency_coherence_band    : float | None
    fluency_coherence_feedback: str | None
    lexical_resource_band     : float | None
    lexical_resource_feedback : str | None
    grammatical_range_band    : float | None
    grammatical_range_feedback: str | None
    pronunciation_band        : float | None
    pronunciation_feedback    : str | None
    examiner_summary          : str | None
    errors                    : dict | None
```

### Get LiveKit Token

```python
# POST /speaking/lk-token  (Pro only)
# Response
{
    "token"     : str,   # LiveKit JWT
    "room_name" : str,   # "speaking-{user_id}-{timestamp}"
    "ws_url"    : str    # LIVEKIT_URL from config
}
```

### Get Dashboard

```python
# GET /dashboard  (accept ?lang=bn)
# Response (free tier)
{
    "is_pro"        : False,
    "total_tests"   : 5,
    "best_overall"  : 7.0,
    "avg_overall"   : 6.5,
    "recent_sessions": [...],
    "score_history" : [...]
}

# Additional fields for Pro tier
{
    "module_avgs"       : {"listening": 6.5, "reading": 7.0, "writing": 5.5, "speaking": 6.0},
    "weak_modules"      : [{"module": "writing", "avg_band": 5.5}],
    "weakness_by_module": {
        "writing": {
            "criteria_avgs"    : {"task_achievement": {"score": 5.0, "label": "Task Achievement"}, ...},
            "weakest_criterion": "coherence_cohesion",
            "weakest_label"    : "Coherence & Cohesion",
            "weakest_score"    : 4.5
        }
    },
    "tips_by_module"    : {"listening": ["tip1"], ...},
    "vocab_tips"        : ["tip1", "tip2"]
}
```

---

## 6. Scoring & Grading Logic

### 6.1 Listening & Reading — Deterministic Scoring

No LLM is involved in scoring listening or reading. Both use the same pattern:

```
submit answers
    → score_answer(question, user_answer) per question  → bool
    → calculate_band(correct, total)                    → float
    → generate_tips(wrong_questions)                    → list[str]
    → (async, if gating passes) generate_feedback_task.delay(...)
```

**`score_answer()` — question type routing:**

| Type | Logic |
|---|---|
| `fill_in_the_blank` / `fill` | Normalize (lowercase, strip punctuation) then exact match against `answer_key` list |
| `multiple_choices` / `mcq` | Option index equality, or normalized text match if key is a string list |
| `multiple_select` | Set equality of selected indices or texts |
| `dropdown` | Exact normalized match |
| `tfng` | Normalize first char: `t` = True, `f` = False, `n` = Not Given |
| `matching_headings` | Lowercase exact match to roman numeral string |
| `matching_info` | Uppercase exact match to paragraph letter |
| `short_answer` | Normalized exact match, or word-set containment for multi-word answers |

**`calculate_band()` — Cambridge official table (scales to 40 questions):**

| Raw score | Band |
|---|---|
| 39–40 | 9.0 |
| 37–38 | 8.5 |
| 35–36 | 8.0 |
| 33–34 | 7.5 |
| 30–32 | 7.0 |
| 26–29 | 6.5 |
| 23–25 | 6.0 |
| 18–22 | 5.5 |
| 16–17 | 5.0 |
| 13–15 | 4.5 |
| 10–12 | 4.0 |
| < 10 | 3.5 |

### 6.2 Writing — Async AI Grading

```
POST /writing/submit
    → creates TestAttempt(status=pending)
    → grade_writing_task.delay(attempt_id, task_data)
    → returns 202 {attempt_id, status: "pending"}

[Celery worker]
    → Claude Haiku grades task1 and task2
    → 4 criteria per task: task_achievement, coherence_cohesion, lexical_resource, grammatical_range
    → each criterion gets: band (0.5 steps, 1.0–9.0), feedback string, list of error annotations
    → overall_band = weighted mean (Task 1: 33%, Task 2: 67%)
    → saves subscores JSON + improvement_tips to TestAttempt
    → marks status=complete (or failed after 3 retries)
```

**Error annotation format:**
```json
{
  "label": "Short label",
  "originalText": "exact phrase from student essay",
  "correctedText": "improved version",
  "note": "one sentence explanation"
}
```

### 6.3 Speaking — Synchronous AI Grading

```
POST /speaking/submit  {transcript, room_name}
    → creates SpeakingAttempt(status=in_progress, transcript=...)
    → calls Claude Sonnet synchronously (grade_speaking_session)
    → 4 criteria overall: fluency_coherence, lexical_resource, grammatical_range, pronunciation
    → each criterion: band + feedback + error list
    → overall_band = mean of 4 criteria
    → saves all fields, marks status=completed
    → returns full SpeakingResultOut immediately
```

Claude model used: `claude-sonnet-4-6` (higher quality for live session evaluation).

### 6.4 Feedback Gating

LLM-generated tips for listening/reading are only triggered under specific conditions to control costs:

```python
# app/services/feedback_gating.py
BAND_DELTA_THRESHOLD = 0.5
ATTEMPTS_THRESHOLD   = 5

def should_generate_llm_feedback(user, module, current_band) -> bool:
    state = user.feedback_state.get(module)  # {last_band, last_attempt_number}
    if not state:
        return True   # first ever attempt for this module
    if current_band - state["last_band"] >= BAND_DELTA_THRESHOLD:
        return True   # meaningful improvement
    total_attempts = count_user_attempts(user, module)
    if total_attempts - state["last_attempt_number"] >= ATTEMPTS_THRESHOLD:
        return True   # been a while
    return False
```

When triggered, `generate_feedback_task` calls Claude Haiku to produce 3 targeted tips and overwrites the rule-based tips on the attempt. On failure, rule-based tips remain visible.

---

## 7. Celery Task Queue

**Broker & backend:** Redis (from `REDIS_URL`). TLS is auto-detected from `rediss://` prefix.

**Worker pool:** `solo` on Windows, `prefork` on Linux (production).

**Config:**
```python
celery_app.conf.update(
    task_serializer       = "json",
    result_serializer     = "json",
    accept_content        = ["json"],
    timezone              = "UTC",
    task_acks_late        = True,
    task_reject_on_worker_lost = True,
)
```

### Task Reference

| Task | Retries | Retry delay | Triggered by |
|---|---|---|---|
| `grade_writing_task` | 3 | 10s | `POST /writing/submit` |
| `grade_speaking_task` | 3 | 10s | `POST /speaking/submit` (legacy flow) |
| `generate_feedback_task` | 2 | 10s | `POST /listening/submit` or `/reading/submit` when gate passes |
| `generate_question_tips_task` | 1 | 30s | `POST /admin/listening\|reading/tests/{id}/generate-tips` |

### Async Writing Flow (detailed)

```
1.  POST /writing/submit  →  FastAPI handler
2.  Create TestAttempt(status=pending, module=writing)
3.  fire  grade_writing_task.delay(attempt_id, task_data)
4.  Return {attempt_id, status: "pending"}

5.  [Celery] attempt.status = "grading"
6.  [Celery] grade_writing(task1_prompt, task1_response, task2_prompt, task2_response)
             → Claude Haiku call (~1-2s, max_tokens=2500)
7.  [Celery] Parse JSON response
8.  [Celery] attempt.subscores = {task1: {...}, task2: {...}}
9.  [Celery] attempt.overall_band = weighted_mean
10. [Celery] attempt.improvement_tips = [...]
11. [Celery] attempt.status = "complete"
12. [Celery] if parent session all 4 complete → send email

Frontend polls GET /writing/attempts/{attempt_id} every ~2s until status != "pending"
```

### Run Celery Worker

```bash
celery -A app.tasks.grading.celery_app worker --loglevel=info --concurrency=2
```

---

## 8. Speaking Agent

**File:** `speaking_agent.py` (root of repo)

The speaking agent is a **standalone process** that runs alongside FastAPI. It listens on LiveKit Cloud for dispatched rooms and acts as the IELTS examiner.

### Stack

| Component | Technology |
|---|---|
| WebRTC transport | LiveKit (livekit-agents 1.x) |
| Speech-to-text | Deepgram Nova-2 (`DEEPGRAM_API_KEY`) |
| LLM | GPT-4o-mini (`OPENAI_API_KEY`) |
| Text-to-speech | OpenAI TTS `tts-1` model (`OPENAI_API_KEY`) |

### Personas

The agent randomly picks one of 4 examiners per session:

| Name | Voice | Gender |
|---|---|---|
| Sarah | `nova` | female |
| Claire | `shimmer` | female |
| James | `echo` | male |
| Michael | `onyx` | male |

### Agent Architecture

```python
class IELTSExaminer(Agent):
    async def on_enter(self):
        # Greets candidate, introduces self by name, asks for full name
        await self.session.generate_reply(instructions="...")

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    persona = random.choice(PERSONAS)
    session = AgentSession(
        stt = deepgram.STT(model="nova-2"),
        llm = lk_openai.LLM(model="gpt-4o-mini"),
        tts = lk_openai.TTS(model="tts-1", voice=persona["voice"]),
    )
    # Publish transcript to data channel so frontend can collect it
    @session.on("conversation_item_added")
    def on_item_added(event):
        asyncio.ensure_future(_publish_transcript(ctx, role, text))

    await session.start(room=ctx.room, agent=IELTSExaminer(name=persona["name"]))
```

### Running the Agent

```bash
# Development
python speaking_agent.py dev

# Production (auto-connects to LiveKit Cloud, listens for room dispatch)
python speaking_agent.py start
```

**Environment variables required (same as main API):**
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`

**Dependencies** (separate from main app — `requirements.agent.txt`):
```
livekit-agents>=1.6
livekit-plugins-deepgram
livekit-plugins-openai
livekit-api
```

---

## 9. Services Reference

| File | Purpose |
|---|---|
| `app/services/writing_grader.py` | `grade_writing(...)` — calls Claude Haiku, returns per-task bands + errors + tips |
| `app/services/speaking_grader.py` | `grade_speaking(part_responses)` — calls Claude Haiku for legacy speaking (Celery path) |
| `app/services/listening_scorer.py` | `score_answer()`, `calculate_band()`, `generate_tips()` — deterministic, no LLM |
| `app/services/reading_scorer.py` | Same as above for reading, handles both old (int) and new (list) answer key formats |
| `app/services/feedback_gating.py` | `should_generate_llm_feedback()` — decides whether to spend tokens on tips |
| `app/services/feedback_generator.py` | `generate_feedback(module, data)` — Claude Haiku call for improvement tips |
| `app/services/question_tips_generator.py` | `generate_listening_question_tip()`, `generate_reading_question_tip()` — batch tip generation per question |
| `app/services/storage.py` | `upload_audio()`, `delete_audio()` — Cloudflare R2 via boto3 S3-compatible API |
| `app/services/email.py` | `send_email_sync()`, `build_test_complete_email()`, `build_referral_signup_email()` — Resend integration |

---

## 10. Auth Flow

All protected endpoints use the `get_current_user` FastAPI dependency.

```
Request: Authorization: Bearer <Firebase_ID_token>

1. HTTPBearer scheme extracts the token string
2. firebase_auth.verify_id_token(token) → decoded dict
3. Extract: firebase_uid, email, full_name from decoded token
4. Look up User by firebase_uid in DB
5. If not found → look up by email (handles firebase_uid rotation edge case)
6. If still not found → create new User (auto-create on first login)
7. If email changed → update user.email
8. Return User object → available to route handler as dependency
```

**Admin check:** Separate `get_current_admin` dependency that calls `get_current_user` then asserts `user.is_admin`.

**Pro check:** Done inline in route handlers via `user.subscription == SubscriptionTier.pro`, or via `isProUser()` helper in frontend.

---

## 11. Session Flow

A `TestSession` tracks a student's progress through all 4 modules of a full IELTS test.

```
1. Student clicks "Start Test"
   POST /sessions/start  {ielts_test_id}
   → returns {session_id, current_module: "listening", status: "in_progress"}

2. For each module (listening → reading → writing → speaking):
   a. Load module test:  GET /listening/tests/{test_id}
   b. Start timer:       POST /sessions/{id}/start-module
   c. Student completes the module
   d. Submit answers:    POST /listening/submit  (or writing/speaking equivalent)
   e. Complete module:   POST /sessions/{id}/complete-module
      → links attempt_id to session, records band score, advances current_module

3. After all 4 modules:
   session.status = "completed"
   session.completed_at = now()
   Email sent via Resend with overall band scores

4. Results page:  GET /sessions/{id}/results
   → returns all 4 module attempt results in one response

Stale session cleanup: background task runs hourly, deletes in_progress sessions
with no last_activity_at update for 12+ hours.
```

**Time limits** are enforced on the server: `GET /sessions/{id}/time-remaining` returns seconds left. Frontend redirects to submit when this reaches 0.

---

## 12. Running Locally

### 1. Prerequisites

- Python 3.11+
- PostgreSQL database (Supabase free tier works)
- Redis (local or Redis Cloud free tier)
- Firebase project with service account JSON
- Anthropic API key

### 2. Environment Setup

```bash
cp .env.example .env
# Edit .env with all required variables (see Section 2)
```

### 3. Install Dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS
pip install -r requirements.txt
```

### 4. Run Database Migrations

```bash
alembic upgrade head
```

### 5. Start FastAPI Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

API available at `http://localhost:8000`
Swagger docs at `http://localhost:8000/docs`

### 6. Start Celery Worker (for writing grading)

```bash
celery -A app.tasks.grading.celery_app worker --loglevel=info --concurrency=2 --pool=solo
```

(`--pool=solo` required on Windows)

### 7. Start Speaking Agent (optional)

```bash
pip install -r requirements.agent.txt
python speaking_agent.py dev
```

---

## 13. CI/CD Pipeline

**File:** `.github/workflows/deploy.yml`

### Triggers

- Push to `main` branch

### Jobs

```
build-and-deploy
    ├── 1. Checkout code
    ├── 2. Authenticate to GCP (Workload Identity Federation)
    │       google-github-actions/auth@v2  with  token_format: access_token
    ├── 3. Login to Artifact Registry
    │       docker/login-action@v3  with  oauth2accesstoken
    ├── 4. Build Docker image
    │       docker build -t {REGION}-docker.pkg.dev/{PROJECT}/ielts-backend/api:latest .
    ├── 5. Push to Artifact Registry
    │       docker push ...
    ├── 6. Deploy to Cloud Run
    │       gcloud run deploy ielts-backend --image ... --env-vars ...
    ├── 7. Deploy Celery Worker to VM  (SSH)
    │       git pull origin main
    │       pip install -r requirements.txt (hash-cached)
    │       kill old worker + start new:  celery ... worker &
    └── 8. Deploy Speaking Agent to VM  (SSH)
            git pull origin main
            pip install -r requirements.agent.txt (hash-cached)
            kill old agent + start new:  python speaking_agent.py start &
```

### Deployment Targets

| Service | Platform | Notes |
|---|---|---|
| FastAPI API | Google Cloud Run | Auto-scales 1–10 instances, 512 MB memory |
| Celery Worker | GCP e2-small VM | Persistent, SSH deploy |
| Speaking Agent | GCP e2-small VM (same) | Separate venv (`/home/MAHMUD/agent-venv`), 2 GB swap file |

### Pip Install Optimization

To avoid slow pip installs on every deploy, CI caches by requirements file hash:

```bash
REQ_HASH=$(md5sum requirements.txt | cut -d' ' -f1)
HASH_FILE=/home/MAHMUD/.req-hash
if [ ! -f "$HASH_FILE" ] || [ "$(cat $HASH_FILE)" != "$REQ_HASH" ]; then
    pip install -r requirements.txt --quiet
    echo "$REQ_HASH" > "$HASH_FILE"
fi
```

### GitHub Secrets Required

```
GCP_PROJECT_ID
GCP_SA_KEY              (service account JSON for WIF)
GCP_WORKLOAD_IDENTITY_PROVIDER
CELERY_VM_HOST          (external IP of VM)
CELERY_VM_USER
CELERY_SSH_KEY          (private SSH key)

# Forwarded as env vars to Cloud Run and VMs:
DATABASE_URL
REDIS_URL
ANTHROPIC_API_KEY
FIREBASE_SERVICE_ACCOUNT_B64
LEMONSQUEEZY_API_KEY
LEMONSQUEEZY_WEBHOOK_SECRET
LEMONSQUEEZY_PRO_VARIANT_ID
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
R2_BUCKET_NAME
R2_PUBLIC_URL
OPENAI_API_KEY
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
LIVEKIT_URL
DEEPGRAM_API_KEY
RESEND_API_KEY
```
