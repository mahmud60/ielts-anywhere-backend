# IELTS Anywhere — Backend

Production-grade AI assessment backend for the IELTS Anywhere platform. Provides LLM-powered grading for Writing and Speaking sections, returning structured band scores with detailed linguistic feedback across all four IELTS criteria.


---

## Architecture overview

```
Client (Next.js)
     │
     ▼
FastAPI (REST API)
     │
     ├── Firebase Auth  ──── JWT validation on every request
     │
     ├── PostgreSQL (Supabase)  ── SQLAlchemy ORM + Alembic migrations
     │
     ├── Celery task queue  ──── async AI grading jobs
     │        │
     │        └── Redis  ──── broker + result backend
     │
     ├── Anthropic API (Claude Haiku)  ── LLM grading + agentic content generation
     │
     └── Cloudflare R2  ──── object storage via AWS S3-compatible API (boto3)
```

Two separate Docker containers: API server (`Dockerfile`) and Celery worker (`Dockerfile.celery`). Deployed to Railway with GitHub Actions CI/CD.

---

## Key features

### Async AI grading pipeline
Writing and Speaking submissions are dispatched as Celery tasks, processed concurrently without blocking the main API. The client polls for results via a task ID. Built to handle burst load without queue overflow.

### LLM-powered scoring
Claude Haiku evaluates responses across all four IELTS band criteria — Task Achievement, Coherence & Cohesion, Lexical Resource, and Grammatical Range & Accuracy — returning a structured JSON response with per-criterion scores and actionable feedback.

### Agentic question generation
An admin endpoint uses Claude to auto-generate Speaking question sets from a topic hint. The model acts as a content agent, producing varied, exam-authentic questions without manual authoring.

### Production-grade data layer
- SQLAlchemy 2.0 ORM with async support (`asyncpg`)
- Alembic for versioned schema migrations
- Pydantic v2 for request/response validation

### Auth & storage
- Firebase Admin SDK for JWT-based authentication
- Google Cloud Firestore for session/user metadata
- Cloudflare R2 for audio/document storage via `boto3` (AWS S3-compatible)

---

## Tech stack

| Layer | Technology |
|---|---|
| API framework | FastAPI 0.135 + Uvicorn |
| Task queue | Celery 5.6 + Redis 7 |
| LLM | Anthropic Claude Haiku |
| Database | PostgreSQL (Supabase) + SQLAlchemy + Alembic |
| Auth | Firebase Admin SDK |
| Cloud storage | Cloudflare R2 via boto3 (AWS SDK) |
| Google Cloud | Firebase, Firestore, GCS |
| Containerisation | Docker (multi-container) |
| CI/CD | GitHub Actions |
| Deployment | Railway |
| Language | Python 3.11+ |

---

## Project structure

```
ielts-anywhere-backend/
├── .github/workflows/      # GitHub Actions CI/CD
├── alembic/                # Database migration scripts
├── app/
│   ├── api/                # FastAPI route handlers
│   ├── core/               # Config, auth, dependencies
│   ├── models/             # SQLAlchemy models
│   ├── schemas/            # Pydantic request/response schemas
│   ├── services/           # Business logic (grading, generation)
│   └── tasks/              # Celery task definitions
├── Dockerfile              # API server container
├── Dockerfile.celery       # Worker container
├── railway.toml            # Railway deployment config
├── alembic.ini
└── requirements.txt
```

---

## Local setup

**Prerequisites:** Python 3.11+, Docker, Redis

```bash
git clone https://github.com/mahmud60/ielts-anywhere-backend
cd ielts-anywhere-backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Copy and fill in environment variables:
```bash
cp .env.example .env
```

Required env vars:
```
ANTHROPIC_API_KEY=
DATABASE_URL=
REDIS_URL=
FIREBASE_CREDENTIALS=
R2_ENDPOINT_URL=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
```

Run with Docker Compose:
```bash
docker compose up --build
```

Or run services separately:
```bash
# API server
uvicorn app.main:app --reload

# Celery worker
celery -A app.tasks.celery_app worker --loglevel=info
```

Apply database migrations:
```bash
alembic upgrade head
```

---

## Author

Mahmudul Hasan — [LinkedIn](https://linkedin.com/in/mahmudhasan60) · [GitHub](https://github.com/mahmud60)

MSc Data Science, FAU Erlangen-Nuremberg