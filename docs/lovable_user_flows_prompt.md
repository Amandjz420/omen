# Lovable prompt — build out all user flows / screens

Standalone, paste-ready prompt for Lovable. It assumes the app is already wired
to the live API per `docs/lovable_integration_fixup.md` (base URL, auth, exact
response shapes). This one adds the **screens, navigation and flows**.

---

## PASTE INTO LOVABLE

The app already talks to the OMEN backend (auth, fetch wrapper, types in place).
Now build out **all screens and user flows** below. Mobile-first for valuers;
tablet/desktop layout for verifiers. Use react-router, TanStack Query, shadcn/ui.
No backend/keys. URLs have no trailing slash. Confidence colors: 🟢 green
`#1a7f37`, 🟡 amber `#b26a00`, 🔴 red `#c0392b`.

### Routing & role landing
On login, call `GET /api/auth/me` and route by `role`:
- `valuer` → `/work` (my valuations)
- `verifier` / `admin` → `/verify` (verification queue)
- `office` → `/cases` (all cases, read-only-ish)
App shell: top bar (logo "OMEN AI", language selector, user menu/logout) + role
nav. Global toasts (use `error.message`), skeleton loaders, empty states.

### VALUER

**/work — My work list**
- `GET /api/valuations?status=` (paginated → `.results`; scoped to me).
- Cards: bank, asset type (`work_order` → service/sub_type), address, status
  badge. Filter chips by status. Tap → `/valuation/:id`.
- "+ New" → pick a work order (`GET /api/work-orders` → `.results`) →
  `POST /api/valuations {work_order_id}` → open it.

**/valuation/:id — Workspace** (tabs: Capture · Form · Report)
- Load `GET /api/valuations/:id`. Header: bank · "service / sub_type" · status;
  **GPS chip** ("Capture location" → `navigator.geolocation` →
  `POST /api/valuations/:id/geo {lat,lng}`; show coords once set).
- **Capture tab** — big buttons, each does presign → upload → confirm
  (`POST /api/media/presign {valuation_id,kind,mime,filename}` →
  upload bytes to `upload_url` via `method`+`headers`, **no auth header** →
  `POST /api/media/confirm {asset_id,size,duration?,lat?,lng?}`):
  - 🎙️ Record voice note (MediaRecorder; kind `audio`; send duration+GPS). List
    notes with play (use `download_url` from `GET /api/valuations/:id/media`).
  - 📷 Photos (`<input capture="environment" multiple>`; kind `photo`; +GPS).
    Thumbnail grid.
  - 📄 Documents (image/PDF; kind `document`). List with filename.
  - ✏️ Sketch (kind `sketch`).
  - Show upload progress; retry on failure; capture must work offline (queue
    uploads).
- **AI actions row** — each `POST /api/valuations/:id/<action>` → `202 {job_id}`
  → poll `GET /api/jobs/:job_id` (~2s, timeout+cancel) with friendly status
  ("Listening to your notes…", "Reading the document…"):
  - Transcribe (`/transcribe`) · Read documents (`/extract-documents`) ·
    Analyze photos (`/analyze-photos`).
  - **Auto-fill form** (`/autofill`, primary) → when done, refetch detail and
    switch to the Form tab.
  - Get market rate (`/market-rate`) → open Market Rate panel.
  - If a job stays `queued` a while, show "queued — processing will start
    shortly" instead of an infinite spinner.

**Form tab — Review & confirm**
- From `GET /api/valuations/:id`, `questions[]` = `{question, answer|null}`.
  Group by `question.detail_category_name`; order by
  `question.detail_category_sequence` then `question.sequence`.
- Top progress bar: counts of 🟢/🟡/🔴 + **"Confirm all green"** bulk.
- Render each by `question.answer_type`: `text`→textarea; `radio`→radio group
  from `options.choices` (fallback free input if none); `checkbox`→multi chips;
  `tabular`→editable mini-table; `sum_of_attribute`/`formula_based_calculation`
  →number input (arrive amber). Color by `answer.confidence`.
- Edit/confirm → `PATCH /api/answers/:answerId {value?,confirmed?}` (returns the
  updated answer; confirming a non-empty red turns it green).
- **"Why?"** drawer per answer: show `answer.evidence[]` ({asset_id,snippet});
  resolve the asset from the media list and play audio / show image / open doc
  via its `download_url`.
- **Market Rate panel**: latest of `GET /api/valuations/:id/market-rates` —
  `result_range {min,max,unit,currency}` + clickable `citations`. "Use as
  adopted rate" → PATCH the relevant rate answer (stays amber).
- Sticky **"Submit for verification"** — disabled while any mandatory answer is
  red; `POST /api/valuations/:id/submit` (on 400 show `error.message`).

**Report tab**
- "Draft comments" (`/draft-comments` job → show `result` text, editable).
- "Generate report" (`/generate-report` job) → then `GET /api/valuations/:id/
  report` → "Download report" opens `{url}`.

**Reverted cases**: if `status === "reverted"`, banner with the latest verifier
reason (from the verification detail `stage_reviews`); valuer edits → resubmit.

### VERIFIER

**/verify — Queue**
- Stage switcher: `legal · social · technical · general · final_approval`.
- `GET /api/verification/queue?stage=<stage>` → `{stage, results:[...]}` (read
  `.results`, NOT paginated). Rows: work order, status, locality. Tap → review.

**/verify/:valuationId — Review**
- `GET /api/verification/:valuationId` → `{answers, stage_reviews,
  ai_risk_flags:[{severity,message,related_answer}]}`.
- Left: answers grouped by category (read-only). Right: **Risk flags** panel
  (severity badge + message + "jump to answer" via `related_answer`).
- Actions: **Approve** `POST /api/verification/:id/:stage/approve`; **Revert**
  `POST /api/verification/:id/:stage/revert {reason}` (reason textarea). On
  success → toast + return to queue. Show `stage_reviews` history/progress.

### ADMIN / OFFICE
- **/cases** — `GET /api/valuations` (all) + status filter.
- **Leads** — list/create `GET|POST /api/leads`; detail PATCH.
- **Work orders** — list/create `GET|POST /api/work-orders`; detail.
- Masters pickers for building work orders: `GET /api/service-types`,
  `/api/service-subtypes?service_type=`, `/api/banks`, `/api/orderers?bank=`.
- Hide verification nav for `office` (not permitted).

### Status → UI badges
Valuation: `draft, in_progress, submitted, in_verification, approved, reverted`.
Job: `queued, running, done, error`. Confidence: `green, amber, red`.

### Acceptance
Valuer: log in → open/seed a case → GPS + audio + photo + document → Auto-fill →
Review (grouped, green/amber/red, evidence drawer) → market rate → Submit (only
when no red mandatory) → generate/download report. Verifier: queue → review with
risk flags → approve/revert. Reverted case shows the reason back on the valuer.

## END PASTE
