# OMEN Assessors — Legacy System Reference (for Claude Code)

**Purpose:** this file is the domain source of truth for OMEN AI. Read it before
designing seed data, models, and the autofill agent. It summarizes the proven
legacy LMS (built 2020) so the new AI platform mirrors real workflow and real
data shapes. The accompanying `seed/questions_seed.csv` (904 real questions) and
`seed/masters_seed.json` are the structured data to load.

## What the business does

OMEN Assessors performs property/asset valuations for banks in India (land,
building, flats, automobiles, plant & machinery). A bank officer requests a
valuation; a field valuer (civil engineer) inspects the property; a structured
form (the "CIF" — Customer Information Form) is filled; it is verified in stages;
a bank-specific report is generated, dispatched, and billed.

## End-to-end flow (the happy path the product must support)

1. **Setup (Masters)** — configuration that drives everything: service types,
   usage of report, scrutiny documents, billing heads, client
   types/divisions/designations, clients (banks), CIF categories, Question Bank,
   bank report headings, report setup.
2. **Lead → Work Order (Lead Manager)** — a bank Orderer places a request → a
   Lead is created → converted to a Work Order carrying client + orderer +
   service type + sub type + bank. This combination determines which questions
   apply.
3. **Valuation (Service Manager)** — the valuer opens the work order, inspects
   the site, and answers the dynamic CIF questionnaire (from the Question Bank).
   In the new product, AI auto-fills this from voice + photos + documents + GPS;
   the valuer confirms.
4. **CIF Verification (6 stages)** — legal → social → technical → general →
   final_approval, with revert to send back for correction. A case must pass all
   stages before report generation.
5. **Bank Report Generation** — answers are arranged into the bank's required
   heading structure (Bank Report Heading + Report Setup) and rendered to a PDF.
6. **Invoice → Dispatch → Pay-in-Receipt** — billing (Billing Heads), dispatch
   (courier/post/email/hand), and a maker-checker payment workflow. (New product
   connects to these later; build stubs only.)

## The data model that matters most: the Question Bank

Every question is tagged with **Service Type + Service Sub Type + Detail Category
+ Answer Type + Sequence**.

The case's bank can select a bank-specific question set: in the legacy system,
some bank names are used as Detail Categories (e.g., "Punjab National Bank",
"Bank of Maharashtra", "Canara Bank") to hold that bank's custom report template.
In `questions_seed.csv` these rows have the bank in BOTH `detail_category` and
`bank_scope`.

**Answer types and how the UI/agent must treat them:**

- **Text** — free text.
- **Radio** — single choice from options.
- **Checkbox** — multiple choices.
- **Tabular** — a small table (rows/cols), e.g., boundaries N/S/E/W, floor-wise
  areas.
- **Sum of Attribute** — a computed subtotal across child line items.
- **Formula Based Calculation** — a derived value (e.g., land value = area ×
  rate; depreciation).

**Detail Categories map to the report parts:** PART A - BANK/PARTY (owner,
documents, purpose), PART B - PRE-SITE VISIT (location, survey, pre-visit), PART C
- ONSITE (boundaries, dimensions, construction, site characteristics), PART D -
POST SITE (valuation calculations, rates, abstract, market value). Some land
templates use Part A - GENERAL, Part C - VALUATION OF LAND, Part M - GUIDE LINE
VALUE, etc.

## Real volumes (for context; full data comes from a legacy export later)

Clients (banks/branches): ~1,288 · Orderers (bank officers): ~1,973 · Question
Bank: ~1,791 · Bank report headings: ~400 · Report setup mappings: ~200 ·
Dispatched reports to date: ~7,377.

The seed files here are a representative subset (904 real questions across Land,
L&B, Flat & Shop, Automobile, including PNB/Maharashtra/Canara variants) — enough
to build and test the full flow. Wire the full import via `import_masters` when
the legacy CSV/JSON export is available.

## Seed files in this repo

- `seed/questions_seed.csv` — columns: `service_type`, `service_sub_type`,
  `bank_scope`, `detail_category`, `answer_type`, `sequence`, `question_text`.
  904 rows.
- `seed/masters_seed.json` — service types/sub types, client
  types/divisions/designations, billing heads, banks, detail categories, answer
  types, dispatch modes, verification stages, plus sample usage-of-report and
  scrutiny documents.

## Notes / data hygiene to handle when seeding

- Detail-category casing is inconsistent in the source (e.g., `PART A - GENERAL`
  vs `Part A - GENERAL`, `PART A - BANK / PARTY` vs `PART A - BANK/PARTY`).
  Normalize on import (trim, collapse spaces around `/`, consistent case) and
  de-duplicate.
- `bank_scope` non-empty means the question applies only when the case's bank
  matches that bank.
- `sequence` controls display order within a detail category; sort by
  (detail_category order, sequence).
- The legacy source has a typo "Redio" → already normalized to "Radio" in the
  CSV.
