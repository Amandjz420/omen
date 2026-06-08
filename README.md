# OMEN AI — Valuation Platform Backend

AI-assisted property-valuation backend for bank valuers (civil engineers) in
India. A valuer visits a property, **speaks in any language**, photographs the
building and documents, and OMEN **auto-fills a structured bank valuation form**
and **generates a bank-specific report**. A human verifier approves it through a
6-stage workflow — **humans always sign off**.

This repository is the **API + AI-orchestration layer only**. The frontend is
built separately (Lovable / React) and talks to this service over REST. All AI
provider keys live here, never in the frontend.

> New to the codebase? Read **[CLAUDE.md](./CLAUDE.md)** for architecture,
> conventions, commands and the full env-var reference.

---

## Tech stack

- Python 3.12 (3.11 works locally), Django 5.x, Django REST Framework
- PostgreSQL (`dj-database-url`; SQLite fallback for local dev)
- `django-storages` + `boto3` → AWS S3 with presigned PUT/GET
- `djangorestframework-simplejwt` (JWT auth; OTP/email later)
- `drf-spectacular` → OpenAPI + Swagger UI at `/api/docs/`
- Central **LLM router** over **DeepInfra** (OpenAI-compatible) + **Perplexity**
- `gunicorn` for production (Railway); AWS S3 for media

## Quick start (local)

```bash
# 1. Virtualenv + deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Env (optional — sensible defaults work out of the box)
cp .env.example .env          # SQLite + mock AI + local file storage by default

# 3. Migrate + seed a clickable demo
python manage.py migrate
python manage.py seed_demo

# 4. Run the API
python manage.py runserver

# 5. In another terminal, run the AI worker (processes queued jobs)
python manage.py run_ai_worker --loop --interval 3
```

- API root: `http://127.0.0.1:8000/api/`
- Swagger UI: `http://127.0.0.1:8000/api/docs/`
- Health check: `http://127.0.0.1:8000/healthz`
- Django admin: `http://127.0.0.1:8000/admin/` (admin / admin12345)

With no AWS or AI keys set, the service runs **fully offline**: media uses a
local filesystem stub and the LLM router returns deterministic mock output
(`AI_MOCK` auto-enables). Plug real keys in via env vars to go live — no code
changes needed.

### Seeded demo users

| Username   | Password        | Role     |
|------------|-----------------|----------|
| `admin`    | `admin12345`    | admin    |
| `valuer`   | `valuer12345`   | valuer   |
| `verifier` | `verifier12345` | verifier |

With `DEV_LOGIN=1` (default in dev), you can also log in **without a password**:
`POST /api/auth/login {"username": "valuer"}`.

## End-to-end smoke test (the milestone-1 flow)

```bash
BASE=http://127.0.0.1:8000

# Dev-login as the seeded valuer
TOKEN=$(curl -s -X POST $BASE/api/auth/login -H 'Content-Type: application/json' \
  -d '{"username":"valuer"}' | python -c "import sys,json;print(json.load(sys.stdin)['access'])")

# See the seeded valuation
VID=$(curl -s $BASE/api/valuations -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;print(json.load(sys.stdin)['results'][0]['id'])")

# Presign + confirm a (fake) media upload
AID=$(curl -s -X POST $BASE/api/media/presign -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d "{\"valuation_id\":\"$VID\",\"kind\":\"audio\",\"mime\":\"audio/wav\",\"filename\":\"site.wav\"}" \
  | python -c "import sys,json;print(json.load(sys.stdin)['asset_id'])")
curl -s -X POST $BASE/api/media/confirm -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"asset_id\":\"$AID\",\"size\":1024}"

# Enqueue autofill, run the worker, poll the job
JID=$(curl -s -X POST $BASE/api/valuations/$VID/autofill -H "Authorization: Bearer $TOKEN" \
  | python -c "import sys,json;print(json.load(sys.stdin)['job_id'])")
python manage.py run_ai_worker --once --batch 5
curl -s $BASE/api/jobs/$JID -H "Authorization: Bearer $TOKEN"

# See the case with AI-filled answers (confidence + evidence)
curl -s $BASE/api/valuations/$VID -H "Authorization: Bearer $TOKEN"
```

## Tests

```bash
pytest                # 19 tests: router, auth, valuation flow (all mocked)
```

## Deployment (Railway)

- Web: `gunicorn omen.wsgi --bind 0.0.0.0:$PORT` (see `Procfile` / `railway.json`)
- Worker: a `worker` process running `run_ai_worker --loop`, **or** a Railway
  cron running `python manage.py run_ai_worker --once --batch 5` every minute.
- Release runs `migrate` + `collectstatic`.
- Set `DJANGO_SETTINGS_MODULE=omen.settings.prod`, `DATABASE_URL` (Postgres
  plugin), `ALLOWED_HOSTS`, `FRONTEND_ORIGIN`, the S3 vars and the AI keys.

See **[CLAUDE.md](./CLAUDE.md)** for the complete env-var table and the API
contract.

## License

Proprietary — internal project.
