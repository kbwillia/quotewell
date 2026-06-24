# NOTES.md

~5 minute read. Assumptions, tradeoffs, and what I'd do with more time.

## What I built (under the 3-hour cap)

A single Python CLI (`python pipeline.py`) that:

1. Reads each file in `inbox/`
2. Calls `POST /api/v1/extract` (no hand-transcription)
3. Parses messy model text, normalizes AMS field formats, cross-checks against the source email
4. Submits ready records to `POST /api/v1/records` with `Idempotency-Key`, retries, and `GET` confirmation

**Run:** `node stub/server.js` then `python pipeline.py`

---

## Assumptions

| Assumption | Rationale |
|---|---|
| **Python is acceptable** | Confirmed with QuoteWell; README originally specified TypeScript. |
| **One record per inbox file** | Each `.txt` is one logical submission; idempotency key = `quotewell-{filename}`. |
| **Part 1 errors block AMS submit** | If source email lacks a required field (Tula effective date), we report `needs_review` instead of guessing. |
| **`annualRevenue: null` is valid** | README and Pelican Point email explicitly allow unknown revenue at intake. |
| **PO Box override only when email contrasts facility vs mail** | Avoids false positives (early bug: `"mailing addres"` matched `"mailing address"`). |
| **Pelican effective date `2026-07-01` is acceptable** | Email says "first of next month" (June 3); model date is reasonable though not exact wording. |
| **Stub is deterministic per (body, attempt)** | Retries are safe with idempotency; restart stub resets state for a clean re-run. |
| **Stdlib only** | No `httpx`/`requests` — keeps setup to `python pipeline.py` only. |
| **Max 10 submit attempts** | Enough to survive 429 + 30s hang + malformed 200 in one run; not infinite loop. |

---

## Expected outcomes (4 inbox files)

| File | Expected result | Why |
|---|---|---|
| email_1 | CONFIRMED | Formats normalized; revenue $4.2M matches latest thread correction |
| email_2 | CONFIRMED | Model revenue cleared to `null` (email says TBD) |
| email_3 | CONFIRMED | Mailing address corrected to PO Box from source email |
| email_4 | NEEDS REVIEW | Effective date not confirmed — won't submit invented date |

---

## What I cut (intentionally, for time)

- **Unit tests** — README says not graded on coverage; manual run against stub instead.
- **Structured logging / metrics** — print JSON summaries only.
- **Human review queue UI** — `needs_review` is a CLI status + error message.
- **LLM re-prompt on parse failure** — fail loudly; broker would re-run extraction.
- **Duplicate scan via `GET /api/v1/records`** — idempotency key is the primary guard; list endpoint not wired in.
- **Per-field confidence scores** — warnings list is enough for this scope.
- **Configurable retry policy** — hard-coded max attempts and timeouts.

---

## What I wouldn't ship as-is

1. **Regex-heavy source validation** — works for 4 sample emails but won't generalize to every broker phrasing. Production needs a small rules engine or human-in-the-loop for edge cases.
2. **Fixed 45s POST timeout** — fine for local stub; real AMS may need circuit breakers and async job polling.
3. **No persistent audit trail** — no record of raw model output, overrides, or who approved exceptions. Regulated workflows need attribution (QuoteWell's governability bar).
4. **Tula handling** — blocking submit is defensible, but a production system might create a partial "intake" record with a `pending_effective_date` flag rather than hard fail.

---

## With more time (priority order)

1. **Audit log** — append-only JSON lines: raw extract output, normalized draft, overrides, submit attempts, final GET proof.
2. **Human review path** — write `needs_review` payloads to a folder with a one-line "approve & resubmit" command.
3. **Smarter source validation** — parse email threads chronologically (top = newest) for corrections; separate "mailing" vs "location" fields in schema if AMS supports it.
4. **Post-run duplicate check** — `GET /api/v1/records` count vs confirmed count.
5. **Retry jitter + exponential backoff** — reduce thundering herd on 429.
6. **Parse malformed 200 bodies** — attempt regex extract of `recordId` before blind retry (only if idempotency weren't available).
7. **TypeScript port** — if aligning with Terminal stack; logic would transfer 1:1.

---

## Loom pointers (not recorded here)

**Confident:** Idempotency key + GET confirmation — never trust status code alone; safe retries after 503.

**Unsure:** Tula effective date — chose block over submitting model-invented date; could argue partial intake is better for broker workflow.

---

## Time spent (honest)

- Part 1 (parse, normalize, source validation): ~majority of effort
- Part 2 (retry, idempotency, confirm): ~simpler by design
- Deliberately stopped at "reliable enough for stub" rather than production polish
