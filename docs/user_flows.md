# OMEN AI — User flow catalog

Every user flow the backend currently supports, grouped by role, mapped to the
exact endpoints, statuses and rules. Use this to design/wire the frontend.
Conventions: JWT bearer, JSON, **no trailing slashes**, error envelope
`{"error":{code,message,detail}}`. Lists are paginated `{count,next,previous,
results}` for `/valuations`, `/work-orders`, `/leads`; **plain arrays** for
masters and the valuation sub-resources (`/answers`, `/media`, `/market-rates`).

Roles: `valuer`, `verifier`, `admin`, `office`. Valuers are scoped to their own
assigned cases; verifiers/admin/office see all. `office` cannot access the
verification endpoints.

---

## A. Auth & session (all roles)

| Flow | Endpoint(s) | Notes |
|---|---|---|
| Login | `POST /api/auth/login {username,password}` → `{access,refresh,user}` | Store tokens; attach `Authorization: Bearer`. |
| Dev login | `POST /api/auth/login {username}` (no password) | Only when backend `DEV_LOGIN=1`. |
| Refresh | `POST /api/auth/refresh {refresh}` → `{access}` | On 401, refresh once, else logout. |
| Who am I / landing | `GET /api/auth/me` | Route by `role`: valuer→work list; verifier/admin→queue; office/admin→all cases. |
| Logout | — | Clear tokens locally. |
| Language | — | UI i18n + preferred capture language passed to AI. |

---

## B. Valuer flows (primary, mobile)

1. **My work list** — `GET /api/valuations?status=` (only my assigned cases).
   Card per case: bank, asset type, address, status badge.
2. **Start a case** — `GET /api/work-orders` → `POST /api/valuations
   {work_order_id}` (created `in_progress`, question set initialized red).
3. **Open workspace** — `GET /api/valuations/{id}` → header + GPS +
   `questions[]` (each `{question, answer|null}`).
4. **Capture GPS** — `POST /api/valuations/{id}/geo {lat,lng}`.
5. **Capture media** — for each file, presign → PUT → confirm:
   - `POST /api/media/presign {valuation_id,kind,mime,filename}` →
     `{asset_id,upload_url,method,headers}` (kind ∈ `audio|photo|document|sketch`)
   - upload bytes to `upload_url` via `method` with `headers` (no auth header)
   - `POST /api/media/confirm {asset_id,size,duration?,lat?,lng?}`
   - `GET /api/valuations/{id}/media` → list with `download_url` (play/preview).
   - Sub-flows: voice note (audio+duration+geo), photo (geo), document (PDF/img),
     sketch; upload retry on failure; offline/queued capture.
6. **AI assist** — each `POST` returns `202 {job_id}`; poll `GET /api/jobs/{id}`
   (`queued→running→done|error`):
   - `/transcribe` — voice → text (+ English).
   - `/extract-documents` — OCR + fields.
   - `/analyze-photos` — construction/condition/surroundings.
   - `/autofill` — **key**: fills answers `{value,confidence,evidence}`; refetch
     detail when done.
   - `/market-rate` → then `GET /api/valuations/{id}/market-rates`
     (`result_range{min,max,unit,currency}` + `citations`). "Use as adopted
     rate" = `PATCH` the rate answer (stays amber).
   - `/draft-comments` — narrative text in the job's `result`.
7. **Review & confirm** — group by `question.detail_category_name` (order by
   `detail_category_sequence`, then `sequence`). Render by `answer_type`
   (`text/radio/checkbox/tabular/sum_of_attribute/formula_based_calculation`).
   Show 🟢/🟡/🔴. Edit/confirm `PATCH /api/answers/{id} {value?,confirmed?}` —
   confirming a non-empty red answer flips it green. "Confirm all green" bulk.
   Evidence drawer per answer (`answer.evidence[] = [{asset_id,snippet}]` →
   resolve via media `download_url`).
8. **Submit** — `POST /api/valuations/{id}/submit` → `in_progress`→`submitted`.
   Blocked (400 + reason) while any **mandatory** answer is red.
9. **Report** — `POST /api/valuations/{id}/generate-report` (job) →
   `GET /api/valuations/{id}/report` → open `{url}` (PDF).
10. **Handle revert** — a `reverted` case returns with the verifier's reason
    (in `stage_reviews`); valuer fixes answers and resubmits.

---

## C. Verifier flows (tablet/desktop)

1. **Stage queue** — `GET /api/verification/queue?stage=legal|social|technical|
   general|final_approval` → `{stage, results:[{valuation_id,work_order,status,
   locality}]}`. Stage switcher across the 5 stages.
2. **Open review** — `GET /api/verification/{valuation_id}` → `{answers,
   stage_reviews, ai_risk_flags:[{severity,message,related_answer}]}`. Read-only
   answers grouped by category; risk-flags panel prominent.
3. **Approve** — `POST /api/verification/{id}/{stage}/approve`. `final_approval`
   → valuation `approved`; any earlier stage → `in_verification`.
4. **Revert** — `POST /api/verification/{id}/{stage}/revert {reason}` →
   valuation `reverted` (back to valuer).
5. **Jump to answer** from a risk flag via `related_answer`.
6. **Final report** — view/download after `final_approval`.

---

## D. Admin / office flows

1. **All cases** — `GET /api/valuations` (unscoped) + `?status=` filter.
2. **Leads** — `GET/POST /api/leads`, `GET/PATCH/DELETE /api/leads/{id}`
   (`new→qualified→converted→lost`).
3. **Work orders** — `GET/POST /api/work-orders`, `GET /api/work-orders/{id}`
   (`open→assigned→completed|cancelled`); filter `status/bank/service_type`.
4. **Masters (pickers)** — `GET /api/service-types`,
   `/api/service-subtypes?service_type=`, `/api/banks`, `/api/orderers?bank=`,
   `/api/questions?service_type=&sub_type=&bank=`.
5. Note: verification endpoints require valuer/verifier/admin — **office is
   excluded**.

---

## E. Lead → Work Order → Valuation pipeline

Create lead → qualify → convert to a **work order** (bank + orderer +
service_type + sub_type → this fixes which questions apply) → create a
**valuation** from the work order → assign a valuer → (Valuer flows B).

---

## F. State machines (UI reference)

- **Valuation:** `draft → in_progress → submitted → in_verification →
  approved`; any stage **revert** → `reverted` → (valuer edits) → resubmit.
- **Verification stage review:** `pending → approved | reverted`.
- **AI job:** `queued → running → done | error`. Handle a stuck-`queued` state
  gracefully (means no worker is running).
- **Answer confidence:** `red` (missing) → `amber` (AI-suggested) → `green`
  (confirmed / directly supported).
- **Lead:** `new → qualified → converted → lost`.
- **Work order:** `open → assigned → completed | cancelled`.

---

## G. Cross-cutting / edge flows

- Pagination: read `.results` for `/valuations|/work-orders|/leads`; plain arrays
  elsewhere.
- Error envelope `{"error":{code,message,detail}}` → toast `message`.
- Job polling: ~2s interval, with timeout + cancel; no-worker fallback copy.
- Upload failures: retry button + progress.
- Per-screen loading / empty / error states.
- Token expiry → silent refresh → logout on failure.
