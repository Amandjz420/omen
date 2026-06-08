# Lovable follow-up prompt — wire the app to the LIVE backend (authoritative contract)

Paste the block below into the existing Lovable project (the one built from the
first prompt). It corrects the API contract to exactly match the running Django
backend and makes the app runnable end-to-end.

---

## PASTE INTO LOVABLE

You already built the OMEN AI frontend. Now make it integrate with the **live
backend** and fix the data contract to match it **exactly**. The backend is real
and authoritative — adapt the frontend to it (do not change endpoint paths). Keep
everything frontend-only (no Supabase/Cloud/keys).

### 0. Make it runnable
- Set env var `VITE_API_BASE_URL=https://omen.up.railway.app` (read via
  `import.meta.env.VITE_API_BASE_URL`; never hardcode).
- The backend already allows CORS from `*.lovable.app` and `omen.devmate.in`, so
  the Lovable preview/published app works with no backend change. (If you run on
  `localhost`, that origin isn't allowed by the prod backend — use the Lovable
  preview, or ask the backend owner to add your localhost origin.)
- **Seeded test users** (auto-created): `valuer / valuer12345` (role valuer),
  `verifier / verifier12345` (verifier), `admin / admin12345` (admin).
- **Dev-login button**: call `POST /api/auth/login` with just `{username:"valuer"}`
  (no password). This only succeeds if the backend has `DEV_LOGIN=1`; otherwise
  use the username+password above. Don't invent a "dev flag" field — the dev path
  is simply an empty/missing password.

### 1. Hard rules that were wrong before — fix these
1. **No trailing slashes.** The API rejects/redirects trailing slashes (a 301 can
   drop the Authorization header or body). Always call e.g. `/api/valuations`,
   never `/api/valuations/`.
2. **Error envelope:** every error is `{"error":{"code","message","detail"}}`.
   The fetch wrapper must throw with `error.message` and toast it.
3. **Pagination is NOT uniform:**
   - **Paginated** `{count,next,previous,results:[...]}`: `GET /api/valuations`,
     `/api/work-orders`, `/api/leads`. Read `.results`.
   - **Plain arrays** (no wrapper): all masters (`/api/service-types`,
     `/api/service-subtypes`, `/api/banks`, `/api/orderers`, `/api/questions`)
     and the valuation sub-resources `/api/valuations/{id}/answers`, `/media`,
     `/market-rates`. Use the array directly.
4. **`answer_type` values are lowercase enum strings**, not display names:
   `text`, `radio`, `checkbox`, `tabular`, `sum_of_attribute`,
   `formula_based_calculation`. Switch on these exact strings.
5. **`options` may be empty.** Many seeded questions have `options = {}`. When a
   `radio`/`checkbox` has no `options.choices`, render a free-text/segmented
   fallback instead of an empty control. When present, choices are
   `options.choices = [{value, label}]`.
6. **`confidence`** is `"green" | "amber" | "red"` (lowercase).

### 2. Exact response shapes (TypeScript types for `src/lib/api.ts`)
```ts
type Role = "valuer" | "verifier" | "admin" | "office";
type Confidence = "green" | "amber" | "red";
type AnswerType = "text" | "radio" | "checkbox" | "tabular"
  | "sum_of_attribute" | "formula_based_calculation";

interface User { id: string; username: string; email: string;
  first_name: string; last_name: string; role: Role; phone: string; }
interface LoginResponse { access: string; refresh: string; user: User; }

interface Paginated<T> { count: number; next: string | null;
  previous: string | null; results: T[]; }

interface ValuationListItem { id: string; work_order: string;
  work_order_reference: string; bank_name: string; status: string;
  assigned_valuer: string | null; latitude: string | null;
  longitude: string | null; address: string; locality: string; created_at: string; }

interface Question { id: string; text: string; answer_type: AnswerType;
  options: { choices?: { value: string; label: string }[] } | Record<string, unknown>;
  sequence: number; is_mandatory: boolean;
  detail_category: string; detail_category_name: string;
  detail_category_sequence: number; bank: string | null; }

interface Answer { id: string; valuation: string; question: string;
  question_text: string; answer_type: AnswerType; value: unknown;
  confidence: Confidence; confirmed: boolean;
  evidence: { asset_id: string; snippet: string }[];
  ai_filled: boolean; updated_at: string; }

// GET /api/valuations/{id}  — questions MERGED with answers (note the nesting!)
interface ValuationDetail {
  id: string; status: string; assigned_valuer: string | null;
  latitude: string | null; longitude: string | null; address: string; locality: string;
  work_order: { id: string; reference: string; bank: { id: string; name: string };
    service_type: { id: string; name: string };
    sub_type: { id: string; name: string } | null; property_address: string };
  questions: { question: Question; answer: Answer | null }[];
  created_at: string;
}

interface MediaAsset { id: string; valuation: string;
  kind: "audio" | "photo" | "document" | "sketch"; mime: string; filename: string;
  size: number | null; duration: number | null; latitude: string | null;
  longitude: string | null; uploaded: boolean;
  transcript: unknown; extraction: unknown;
  download_url: string | null; created_at: string; }

interface PresignResponse { asset_id: string; upload_url: string;
  method: "PUT"; headers: Record<string, string>; }

interface Job { id: string; valuation: string; task: string;
  status: "queued" | "running" | "done" | "error";
  result: unknown; error: string;
  created_at: string; started_at: string | null; finished_at: string | null; }

interface MarketRate { id: string; valuation: string; query: string;
  result_range: { min: number; max: number; unit: string; currency: string } | null;
  citations: (string | Record<string, unknown>)[]; created_at: string; }

// GET /api/verification/queue?stage=
interface VerificationQueue { stage: string;
  results: { valuation_id: string; work_order: string; status: string; locality: string }[]; }
// GET /api/verification/{valuation_id}
interface VerificationDetail { valuation_id: string; status: string;
  answers: Answer[]; stage_reviews: unknown[];
  ai_risk_flags: { severity: string; message: string; related_answer: string | null }[]; }
```

### 3. Review screen — fix the rendering
`GET /api/valuations/{id}` returns `questions: [{ question, answer }]` (the
answer is **nested and nullable**, not flattened). For each item:
- Group by `question.detail_category_name`; order groups by
  `question.detail_category_sequence`, items by `question.sequence`.
- Confidence/`confirmed`/`value`/`evidence` come from `answer` (treat `null` as a
  red, unanswered field).
- Render the input by `question.answer_type` (lowercase values above).
- Evidence drawer: `answer.evidence[]` is `{asset_id, snippet}`. Resolve the
  asset via `GET /api/valuations/{id}/media` and use that asset's
  `download_url` (already a signed URL — use it directly in `<img>`/`<audio>`).
- Edit/confirm: `PATCH /api/answers/{answer.id}` with `{value?, confirmed?}` →
  returns the updated `Answer`. Confirming a non-empty answer clears red→green.
- **Submit** `POST /api/valuations/{id}/submit`: on `400`, show
  `error.message` (it lists how many required fields are still red) and keep the
  button disabled until they're resolved.

### 4. Media upload — DB-backed presign (same 3-step contract)
1. `POST /api/media/presign {valuation_id, kind, mime, filename}` →
   `{asset_id, upload_url, method, headers}`.
2. Send the raw file bytes to `upload_url` using `method` (PUT) with `headers`.
   **Do NOT attach the Authorization/Bearer header to this request** — the URL is
   pre-signed (the upload may be same-host; the auth interceptor must skip it).
3. `POST /api/media/confirm {asset_id, size, duration?, lat?, lng?}` → returns the
   `MediaAsset` (with `download_url`).
4. Refresh `GET /api/valuations/{id}/media`.
(Storage is currently the backend's own signed store, not S3 — but the contract
is identical, so this flow is unchanged and works out of the box.)

### 5. AI jobs — polling
Each AI action returns `202 { job_id }`. Poll `GET /api/jobs/{job_id}` every ~2s
until `status` is `done` or `error` (with a timeout + cancel). Then:
- `autofill` done → refetch `GET /api/valuations/{id}` and go to Review.
- `market-rate` done → read `GET /api/valuations/{id}/market-rates` (array;
  newest last) → show `result_range {min,max,unit,currency}` + `citations`.
  "Use as adopted rate" = `PATCH` the relevant rate answer's `value` (stays amber).
- `generate-report` done → `GET /api/valuations/{id}/report` → `{url}` → open it.
- `draft-comments` done → the text is in the job's `result`.
> Note: jobs only progress if the backend worker is running. If a job stays
> `queued` for long, surface a gentle "processing is queued" state rather than
> spinning forever.

### 6. Verification (verifier/admin only)
- Queue: `GET /api/verification/queue?stage=legal|social|technical|general|final_approval`
  → `{stage, results:[...]}` (read `.results`; it is **not** the paginated shape).
- Detail: `GET /api/verification/{valuation_id}` → `{answers, stage_reviews,
  ai_risk_flags:[{severity,message,related_answer}]}`. Show risk flags prominently;
  "jump to answer" maps `related_answer` → the answer id.
- `POST /api/verification/{valuation_id}/{stage}/approve` and
  `POST /api/verification/{valuation_id}/{stage}/revert {reason}`.
- Route by `GET /api/auth/me` role: valuer→valuations, verifier/admin→queue.

### 7. Creating / listing work
- Valuer home: `GET /api/valuations` (paginated, scoped to me). The seeded demo
  case `WO-DEMO-001` (L & B / State Bank of India) is already assigned to the
  `valuer` user.
- To start a new case from a work order: `GET /api/work-orders` (paginated) →
  `POST /api/valuations {work_order_id}`.

### 8. Acceptance (must work against the live API)
Log in as `valuer` → open the seeded valuation → capture GPS → record audio /
add photo / upload a document (presign→PUT→confirm) → **Auto-fill** → poll →
Review screen shows ~222 questions grouped by Part with amber answers + evidence →
edit/confirm → market rate with citations → Submit. Log in as `verifier` → open
the queue → see risk flags → approve/revert.

## END PASTE
