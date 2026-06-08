# Lovable integration prompt — OMEN AI frontend

Paste the block below into Lovable. It connects the React app to the existing
OMEN backend at `https://omen.up.railway.app`. (CORS for `*.lovable.app` and
`omen.devmate.in` is already configured on the backend.)

> **Backend prerequisites for a working end-to-end demo**
> 1. Seed data + users on Railway (one-off): `python manage.py seed_demo`
>    → creates `admin/admin12345`, `valuer/valuer12345`, `verifier/verifier12345`
>    and one L&B/SBI valuation. (Or set env `DEV_LOGIN=1` for passwordless login.)
> 2. Media now works **without S3**: files are stored in the DB (mock S3) and
>    served via signed URLs, so upload/download work out of the box. Set
>    `PUBLIC_BASE_URL=https://omen.up.railway.app` so signed URLs are absolute.
>    (Add AWS S3 env vars later to switch to real S3 — same frontend contract.)

---

## PASTE INTO LOVABLE

Build a mobile-first React web app called **OMEN AI** for bank property valuers
and verifiers in India. **Do NOT build a backend or database** — a REST API
already exists at `https://omen.up.railway.app`. Integrate with it exactly as
specified. Use a typed API client, React Query (or SWR) for data fetching, and
react-router. JSON everywhere. **URLs have NO trailing slash.**

### API base & auth
- Base URL: `https://omen.up.railway.app/api`
- Auth is JWT. `POST /auth/login {username, password}` → `{access, refresh, user}`.
  Store both tokens in localStorage. Send `Authorization: Bearer <access>` on
  every request.
- On any `401`, call `POST /auth/refresh {refresh}` → `{access}`, retry once; if
  refresh fails, clear tokens and route to /login.
- All errors use this envelope: `{"error": {"code", "message", "detail"}}` —
  surface `error.message` as a toast.
- `GET /auth/me` → the current `{id, username, email, role, phone}`. Roles:
  `valuer`, `verifier`, `admin`, `office`. Drive navigation by role:
  valuers capture/review their cases; verifiers approve/revert; admin/office see all.

### Response shapes
- **Paginated** (`{count, next, previous, results}`): `GET /valuations`,
  `/leads`, `/work-orders`.
- **Plain arrays**: all masters (`/service-types`, `/service-subtypes`,
  `/banks`, `/orderers`, `/questions`) and the valuation sub-resources
  (`/answers`, `/media`, `/market-rates`).

### Screens & flow

**1. Login** — username/password form → store tokens → load `/auth/me` → redirect
by role.

**2. Valuations list** (`GET /valuations?status=`) — cards showing
`work_order_reference`, `bank_name`, `status`, `locality`. Tap → detail.
Statuses: `draft, in_progress, submitted, in_verification, approved, reverted`.
(To create one: `POST /valuations {work_order_id}` using a work order from
`GET /work-orders`.)

**3. Valuation detail** (`GET /valuations/{id}`) — returns the case header + GPS +
the **question set merged with current answers**:
```
{ id, status, latitude, longitude, address, locality,
  work_order: { id, reference, bank:{id,name}, service_type:{id,name}, sub_type:{id,name}|null },
  questions: [ { question: { id, text, answer_type, options, sequence, is_mandatory,
                             detail_category_name, detail_category_sequence, bank },
                 answer: { id, value, confidence, confirmed, evidence, ai_filled } | null } ] }
```
Group questions by `detail_category_name`, ordered by
`detail_category_sequence` then `sequence`. Render inputs by `answer_type`:
`text`→text field; `radio`→single select from `options.choices` (`{value,label}`);
`checkbox`→multi-select; `tabular`→editable rows; `sum_of_attribute` /
`formula_based_calculation`→read-only computed (always review). Show a confidence
chip per answer: **green** (confident), **amber** (review), **red** (missing).
Mark `is_mandatory` questions with a required indicator.

**4. Capture step** (valuer):
- **GPS**: `POST /valuations/{id}/geo {lat, lng}` (from browser geolocation).
- **Media (direct browser→S3, 3 steps):**
  1. `POST /media/presign {valuation_id, kind, mime, filename}` →
     `{asset_id, upload_url, method, headers}`. `kind` ∈ `audio|photo|document|sketch`.
  2. Upload the file bytes to `upload_url` using `method` (PUT) with the returned
     `headers` — **no auth header** (the URL is pre-signed). Do not route it
     through the API client's auth interceptor.
  3. `POST /media/confirm {asset_id, size, duration?, lat?, lng?}`.
- List uploaded media: `GET /valuations/{id}/media` (each has a `download_url`).
- Provide a one-tap "record voice note" (audio), "photo", and "document" upload.

**5. AI actions** — each returns `{job_id}` (HTTP 202); then poll
`GET /jobs/{job_id}` every ~1.5s until `status` is `done` or `error`, showing a
spinner. Buttons:
- `POST /valuations/{id}/transcribe` — voice → text (+ English).
- `POST /valuations/{id}/extract-documents` — OCR docs.
- `POST /valuations/{id}/analyze-photos` — building/condition analysis.
- `POST /valuations/{id}/autofill` — **the key step**: fills the question set with
  `{value, confidence, evidence}`. After it's `done`, refetch the valuation detail.
- `POST /valuations/{id}/market-rate` — then show `GET /valuations/{id}/market-rates`
  (`result_range {min,max,unit,currency}` + `citations[]`). Suggest only.
- `POST /valuations/{id}/draft-comments` — narrative remarks (in job `result`).
- `POST /valuations/{id}/generate-report` — then `GET /valuations/{id}/report`
  → `{url}` (open the presigned PDF in a new tab).
Job shape: `{id, task, status, result, error, started_at, finished_at}`.

**6. Review & confirm** (valuer) — `GET /valuations/{id}/answers` (array of
`{id, question_text, answer_type, value, confidence, confirmed, evidence, ai_filled}`).
Let the valuer edit/confirm each: `PATCH /answers/{id} {value?, confirmed?}`.
Confirming a valid answer clears `red`. Show `evidence[]`
(`{asset_id, snippet}`) as "why" links back to the source media.

**7. Submit** — `POST /valuations/{id}/submit`. If any mandatory answer is still
`red`, the API returns `400` with the reason — show it and block. On success the
case moves to verification.

**8. Verification** (verifier/admin) — a 6-stage pipeline
`legal → social → technical → general → final_approval` (+ `revert`):
- Queue: `GET /verification/queue?stage=legal` → `{stage, results:[{valuation_id,
  work_order, status, locality}]}`.
- Review: `GET /verification/{valuation_id}` → `{answers[], stage_reviews[],
  ai_risk_flags:[{severity, message, related_answer}]}`. Show the AI risk flags
  prominently.
- Approve: `POST /verification/{valuation_id}/{stage}/approve`.
- Revert: `POST /verification/{valuation_id}/{stage}/revert {reason}` (sends back
  to the valuer).

**9. Report** — `GET /valuations/{id}/report` → `{url}`; show a "Download report"
button once `final_approval` is done.

### Masters (for pickers / building work orders)
- `GET /service-types` · `GET /service-subtypes?service_type={id}` ·
  `GET /banks` · `GET /orderers?bank={id}`
- `GET /questions?service_type={id}&sub_type={id}&bank={id}` → the ordered
  template (same shape as `questions[].question` above).

### UX notes
- Mobile-first; large tap targets; works one-handed in the field.
- Optimistic UI where safe; always refetch the valuation detail after `autofill`
  or any answer edit.
- Confidence colours: green `#1a7f37`, amber `#b26a00`, red `#c0392b`.
- Show the Swagger reference at `https://omen.up.railway.app/api/docs/` for any
  field you're unsure about.

## END PASTE
