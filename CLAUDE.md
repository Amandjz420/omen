# CLAUDE.md — OMEN AI backend

Guidance for working in this repo (for Claude Code and humans). Keep this file
updated as the architecture evolves.

## What this is

The **API + AI-orchestration layer** for OMEN AI, an AI-assisted property
valuation platform for Indian bank valuers. Valuers speak (any language) and
photograph the property + documents; the system auto-fills a structured bank
form and produces a bank-format report. A human verifier signs off via a
6-stage workflow. **AI assists; humans always confirm.** The React/Lovable
frontend talks to this service over REST. **All provider keys live here.**

## Tech stack

Python 3.12 · Django 5.x · DRF · PostgreSQL (`dj-database-url`, SQLite fallback)
· `django-storages`+`boto3` (S3, presigned PUT/GET) · SimpleJWT · `drf-spectacular`
· `django-cors-headers` · DeepInfra (OpenAI SDK) + Perplexity (`httpx`) ·
`gunicorn` · Railway.

## Project layout

```
omen/settings/{base,dev,prod}.py   # split settings; DJANGO_SETTINGS_MODULE picks one
core/        # BaseModel (uuid pk, created/updated), pagination, exception envelope, RolePermission, seed_demo
accounts/    # custom User (roles: valuer/verifier/admin/office), JWT login/refresh/me, dev-login
masters/     # config: ServiceType/SubType, Bank(=Client), Orderer, ClientDivision/Designation, BillingHead,
             #   DetailCategory, Question Bank, BankReportHeading, ReportSetup; selectors.questions_for();
             #   seed_from_legacy (real data) + import_masters scaffold (full legacy export)
leads/       # Lead, WorkOrder (client+orderer+service+subtype+bank → scopes the question set)
valuations/  # Valuation, MediaAsset, Answer, MarketRateLookup; storage.py (S3 presign + fallback)
ai/          # router.py (THE hub), services.py (task fns), jobs.py (AIJob queue), run_ai_worker,
             #   models AIJob + LLMCall (audit), costs.py
reports/     # generator.py (answers→headings via ReportSetup→HTML→PDF→S3); Invoice/Dispatch/Receipt STUBS
verification/# StageReview, 6-stage queue/approve/revert + AI risk flags
```

## The LLM Router (`ai/router.py`) — the heart

Single entry point for every AI call. **Model/provider choices live ONLY in
`TASK_MODEL_MAP`** (env-overridable) because provider catalogs change monthly.

- `TaskType` enum: ASR, TRANSLATE, CLASSIFY, DOC_EXTRACT, IMAGE_ANALYZE,
  FORM_AUTOFILL, NARRATIVE, RISK_CHECK, MARKET_RATE_SEARCH, EMBED.
- Helpers: `complete(task, messages, *, images, json_schema, valuation, **overrides)`,
  `transcribe(audio_bytes, *, language)`, `embed(texts)`, `search(query, *, deep)`.
- Providers: **DeepInfra** via the `openai` SDK (`base_url` = DeepInfra) for
  chat/vision/audio/embeddings; **Perplexity** via `httpx` for web search.
- Cross-cutting: timeout + retry-with-backoff (`_with_retry`), structured logging,
  safe JSON parsing (`parse_json` strips code fences), and an `LLMCall` audit row
  per call (task, provider, model, tokens, latency, est_cost via `costs.py`,
  valuation_id) so spend is visible per task and per case.
- **Mock mode**: `AI_MOCK=1` (auto-on when no keys) returns deterministic,
  schema-shaped stub output so the whole pipeline runs offline.

### Changing a model
Edit `TASK_MODEL_MAP` in `ai/router.py`, **or** set `AI_MODEL_<TASK>` /
`AI_PROVIDER_<TASK>` env vars (e.g. `AI_MODEL_FORM_AUTOFILL`). Update `costs.py`
if you want accurate spend estimates for a new model.

## AI task functions (`ai/services.py`)

Each is a plain callable taking a `Valuation`; all run through the `AIJob` queue.
`transcribe_valuation_audio`, `extract_documents`, `analyze_photos`,
`autofill_answers` (**the key step**: loads the exact question set for
service+subtype+bank, returns `{value, confidence, evidence[]}` per question,
forces numeric/judgment fields to `amber` — never auto-confirms a valuation
figure), `market_rate` (Perplexity; suggests, never silently auto-fills),
`draft_comments`, `run_risk_checks(valuation, stage)`, `generate_report`.
Registry: `TASK_FUNCTIONS`.

## Async jobs

DB-backed queue (no Celery yet, by design — `enqueue`/`run_job` seam matches a
future Celery task). AI action endpoints enqueue an `AIJob` and return
`{job_id}`; frontend polls `GET /api/jobs/{id}`.

```bash
python manage.py run_ai_worker --once --batch 5      # cron mode (Railway cron, e.g. every minute)
python manage.py run_ai_worker --loop --interval 3   # worker service mode
```

## Commands

```bash
python manage.py migrate
python manage.py seed_from_legacy          # load real masters + 904-row Question Bank from seed/ (idempotent)
python manage.py seed_demo                 # runs seed_from_legacy, then adds users + 1 L&B/SBI valuation
python manage.py import_masters <entity> <file>   # SCAFFOLD only (full legacy export, later)
python manage.py runserver
python manage.py run_ai_worker --loop --interval 3
pytest
```

### Seed data (see `docs/legacy_system_reference.md`)

- **`seed_from_legacy`** loads `seed/masters_seed.json` + `seed/questions_seed.csv`
  idempotently: ServiceTypes, ServiceSubTypes, Banks, ClientDivisions (global),
  ClientDesignations, BillingHeads, normalized+de-duplicated DetailCategories,
  and all **900 distinct** Question Bank rows (904 CSV rows; 4 are exact dupes).
  `bank_scope` → `Question.bank`. ClientTypes/AnswerTypes are *validated* against
  the `ClientKind`/`AnswerType` enums (no rows — they're code enums by design).
  Detail-category normalization: trim, collapse whitespace, remove spaces around
  `/`, uppercase; ordered by JSON sequence with CSV-only categories appended.
- **`seed_demo`** builds a small curated demo on top: admin/valuer/verifier,
  two sample banks (SBI + Canara), a couple of orderers, and one end-to-end
  **L & B valuation for State Bank of India** (renders 222 questions).

### Question-filtering rule (`masters.selectors.questions_for`)

`GET /api/questions?service_type=&sub_type=&bank=` returns the case's question
set: **filter by service_type**; **sub_type** matches the given sub-type *or*
questions with no sub-type; **bank_scope** is empty *or* equals the requested
bank (so bank-agnostic questions always apply, bank-scoped ones only when the
case's bank matches). **Ordered by `detail_category.sequence`, then `sequence`.**
Some legacy banks (PNB, Bank of Maharashtra, Canara) double as detail
categories; those rows carry the bank in both `detail_category` and `bank_scope`.

## Conventions

- Every model inherits `core.models.BaseModel` (UUID pk, `created_at`/`updated_at`).
- DRF ViewSets + routers (`trailing_slash=False` — the API uses **no** trailing
  slashes to match the frontend contract).
- Querysets are **role-scoped**: valuers see only their assigned cases;
  verifiers/admin/office see all.
- Errors use the `{"error": {code, message, detail}}` envelope (`core/exceptions.py`).
- AI code is provider-agnostic — it only talks to `ai.router`.
- Type hints + docstrings on the router, services and core endpoints.
- Prefer clear, boring Django over cleverness.

## Storage & security

- Media in S3 (private bucket); uploads go **browser → S3** via presigned PUT;
  downloads via presigned GET. No media passes through Django.
- `valuations/storage.py` has two backends behind one interface (`USE_S3`
  auto-detects from creds): **S3**, or a **DB-backed "mock S3"** that stores
  bytes in a `StoredBlob` row (Postgres `bytea`) and serves them via signed,
  time-limited URLs to `/api/storage/{upload,download}` — same presign→PUT→confirm
  contract, so the frontend is identical. The DB store survives Railway's
  ephemeral filesystem. Set `PUBLIC_BASE_URL` so worker-generated URLs are absolute.
- CORS restricted to `FRONTEND_ORIGIN` (prod default: the Lovable app
  `https://omtas.lovable.app` + custom domain `https://omen.devmate.in`, plus a
  regex for `*.lovable.app` preview subdomains). Same origins trusted for CSRF.
  All AI/AWS keys are backend env vars only.

## Railway deployment notes

- **Postgres**: add the Railway Postgres plugin and set
  `DATABASE_URL=${{Postgres.DATABASE_URL}}` on the web/worker services. The code
  already reads `DATABASE_URL` (SQLite is only the local fallback); `psycopg` is
  in `requirements.txt`. Migrations run via the release/preDeploy command.
- **Web** `gunicorn omen.wsgi`; **Worker** `run_ai_worker --loop` (or a Railway
  cron running `--once --batch 5`). The job queue is DB-backed (no Celery/Redis).

## API contract (JWT bearer; JSON; no trailing slashes)

```
Auth:        POST /api/auth/login {username,password?}  ·  POST /api/auth/refresh  ·  GET /api/auth/me
Masters:     GET /api/service-types · /api/service-subtypes?service_type= · /api/banks
             GET /api/orderers?bank= · GET /api/questions?service_type=&sub_type=&bank=  (rendered template)
Leads/WO:    GET/POST /api/leads · GET/POST /api/work-orders · GET /api/work-orders/{id}
Valuations:  GET /api/valuations[?status=] · POST /api/valuations {work_order_id}
             GET /api/valuations/{id}            (header + GPS + questions merged with answers)
             POST /api/valuations/{id}/geo {lat,lng} · POST /api/valuations/{id}/submit
Media:       POST /api/media/presign {valuation_id,kind,mime,filename} → {asset_id,upload_url,headers}
             POST /api/media/confirm {asset_id,size,duration?,lat?,lng?}
             GET  /api/valuations/{id}/media
AI (→{job_id}): POST /api/valuations/{id}/{transcribe|extract-documents|analyze-photos|
                 autofill|market-rate|draft-comments|generate-report}
             GET  /api/jobs/{id} → {status,result,error}
Answers:     GET /api/valuations/{id}/answers · PATCH /api/answers/{id} {value,confirmed}
Verify:      GET /api/verification/queue?stage=legal|social|technical|general|final_approval
             GET /api/verification/{valuation_id}
             POST /api/verification/{valuation_id}/{stage}/approve
             POST /api/verification/{valuation_id}/{stage}/revert {reason}
Reports:     GET /api/valuations/{id}/report → {url}   (presigned PDF)
```

Stubs (Invoice / Dispatch / PayInReceipt) exist as empty models — they connect
to the legacy system later; do not build on them now.

## Environment variables

| Var | Default | Purpose |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `omen.settings.dev` | `…dev` local, `…prod` on Railway |
| `SECRET_KEY` | insecure dev key | Django secret (set in prod!) |
| `DEBUG` | `False` (dev: `True`) | debug mode |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | comma list |
| `LOG_LEVEL` | `INFO` | root log level |
| `DATABASE_URL` | — (SQLite fallback) | Postgres URL |
| `FRONTEND_ORIGIN` | `http://localhost:8080` | CORS origin(s), comma list |
| `CSRF_TRUSTED_ORIGINS` | — | prod CSRF origins |
| `DEV_LOGIN` | `False` (dev: `True`) | passwordless login for seeded users |
| `JWT_ACCESS_MINUTES` / `JWT_REFRESH_DAYS` | `60` / `7` | token lifetimes |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | — | S3 creds (unset → local stub) |
| `AWS_STORAGE_BUCKET_NAME` / `AWS_S3_REGION_NAME` | — / `ap-south-1` | S3 bucket |
| `AWS_S3_PRESIGN_EXPIRY` | `3600` | presigned URL TTL (s); also the mock signed-URL TTL |
| `PUBLIC_BASE_URL` | — | absolute base URL of this API, for worker-built media/report URLs |
| `DEEPINFRA_API_KEY` | — | DeepInfra key |
| `DEEPINFRA_BASE_URL` | `https://api.deepinfra.com/v1/openai` | DeepInfra base |
| `PERPLEXITY_API_KEY` | — | Perplexity key |
| `PERPLEXITY_BASE_URL` | `https://api.perplexity.ai` | Perplexity base |
| `AI_MOCK` | auto (`1` if no keys) | force deterministic mock output |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | `60` / `3` | router resilience |
| `AI_MODEL_<TASK>` / `AI_PROVIDER_<TASK>` | — | per-task overrides |
| `PORT` | (Railway) | gunicorn bind port |

## Project assets (domain reference & seed data)

Real reference material from the legacy OMEN Assessors system, kept in-repo:

- **`docs/legacy_system_reference.md`** — domain **source of truth**: the real
  OMEN Assessors valuation workflow (masters → lead/work order → CIF valuation →
  6-stage verification → bank report → invoice/dispatch/receipt), the Question
  Bank data shape, answer-type semantics, real volumes, and data-hygiene notes.
  Read this before designing seed data, models, or the autofill agent.
- **`seed/questions_seed.csv`** — 904 real Question Bank rows. Columns:
  `service_type`, `service_sub_type`, `bank_scope`, `detail_category`,
  `answer_type`, `sequence`, `question_text`. A non-empty `bank_scope` means the
  question applies only when the case's bank matches.
- **`seed/masters_seed.json`** — master data: banks, service sub types, client
  types/divisions/designations, billing heads, detail categories, answer types,
  dispatch modes, verification stages (plus sample usage-of-report and scrutiny
  documents).

These are a representative subset for dev/test; full production volumes
(~1,288 clients / ~1,973 orderers / ~1,791 questions / ~400 headings) load later
via `import_masters` from a legacy export.

## Roadmap seams (intentionally left open)

- **Auth**: OTP/email plug into the same `/api/auth` endpoints (replace dev-login).
- **Jobs**: swap the DB queue for Celery+Redis behind `ai/jobs.py`.
- **Masters import**: implement `import_masters` field mapping once the legacy
  export schema is available (~1,288 clients / 1,973 orderers / 1,791 questions /
  400 headings).
- **Billing**: wire Invoice/Dispatch/PayInReceipt stubs to the legacy system.
- **Router config**: move `TASK_MODEL_MAP` into a DB table for runtime edits.
