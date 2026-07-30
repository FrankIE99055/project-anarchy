# Project Anarchy — Technical Overview

**Irish Real Estate Propensity-to-Sell Prediction Platform**

---

## Table of Contents

1. [What This Application Does](#1-what-this-application-does)
2. [System Architecture](#2-system-architecture)
3. [Data Sources & Pipeline](#3-data-sources--pipeline)
4. [Database Design](#4-database-design)
5. [The Propensity Score Algorithm](#5-the-propensity-score-algorithm)
6. [Risk Factors (Key Drivers) Explained](#6-risk-factors-key-drivers-explained)
7. [AI Layer #1 — Natural-Language Explanation](#7-ai-layer-1--natural-language-explanation)
8. [AI Layer #2 — Live Web Research](#8-ai-layer-2--live-web-research)
9. [API Reference](#9-api-reference)
10. [Frontend Application](#10-frontend-application)
11. [Privacy & GDPR Design Principles](#11-privacy--gdpr-design-principles)
12. [Known Limitations & Roadmap](#12-known-limitations--roadmap)

---

## 1. What This Application Does

Project Anarchy is a data platform that estimates, for almost every residential
property in Ireland, a **"Propensity Score"** — a 0–100 number representing how
statistically likely that property is to come onto the market for sale in the
near future, and *why* (a human-readable list of "Key Drivers").

It does **not** predict anything about a named person. It works entirely at the
**address / property level**, using only publicly available registers and
listings. The core idea is that certain observable, public signals correlate
with an increased likelihood of a sale:

- A property that hasn't changed hands in a very long time (aging owner,
  inherited property, etc.)
- A **retention planning application** (legalizing unauthorized works — a
  classic step taken right before putting a property on the market)
- A property listed on a **derelict / vacant sites register**
- A property that was **rented and is now for sale** ("accidental landlord"
  exiting the rental market)
- A property that has been **relisted for sale multiple times** (didn't sell,
  price problems)
- A property with a **falling asking price**

None of these signals alone is proof of an imminent sale — this is a
probabilistic, explainable heuristic model, not a certainty engine. The whole
design philosophy is: **every score must be traceable back to specific,
public facts**, never a black box.

Current scale: **987,948 properties** tracked, built from:

| Source | Rows |
|---|---|
| Property Price Register (PPR) sales | 792,378 |
| Planning Permissions | 319,280 |
| Daft.ie historical listings | 663,188 |
| Derelict / Vacant Sites registers | 364 |

---

## 2. System Architecture

```mermaid
flowchart TB
    subgraph Sources["Public Data Sources"]
        PPR[Property Price Register]
        PLAN[Planning Permissions - ArcGIS]
        DAFT[Daft.ie scraped listings]
        DERE[Derelict/Vacant Sites registers]
    end

    subgraph Pipeline["data_pipeline/ (Python/pandas)"]
        DL[Download + clean CSVs]
    end

    subgraph DB["Supabase (PostgreSQL + PostGIS)"]
        STAGE[Staging tables]
        CORE[properties / sales_history / planning_permissions /\nderelict_sites / daft_listings]
        SCORE[Propensity Score views\n(percentile-ranked)]
        AIF[ai_research_findings\n(cached AI web research)]
    end

    subgraph Backend["FastAPI backend"]
        API[REST API]
        DS[DeepSeek AI - explanation]
        AR[Tavily + DeepSeek - live research]
    end

    subgraph Frontend["Next.js SaaS frontend"]
        MAP[Map]
        LIST[Search / list]
        DETAIL[Property detail\n(Overview / History / AI)]
        AN[Analytics dashboard]
    end

    Sources --> DL --> STAGE --> CORE --> SCORE
    API --> CORE
    API --> SCORE
    API --> DS
    API --> AR --> AIF
    AR -.writes back.-> CORE
    Frontend --> API
```

**Stack:**

- **Database**: Supabase (managed PostgreSQL 18 + PostGIS), all geodata stored
  as `geography(POINT, 4326)`.
- **ETL / data pipeline**: Python (`pandas`, `requests`), bulk-loaded via
  `psql \copy` into staging tables, then merged into production tables with
  set-based SQL (`INSERT ... SELECT`, `GROUP BY` aggregates) — chosen because
  row-by-row REST API upserts do not scale to hundreds of thousands of rows.
- **Backend**: FastAPI (Python), stateless REST API, talks to Supabase via the
  `supabase-py` client and to DeepSeek via the OpenAI-compatible SDK.
- **Frontend**: Next.js (App Router, TypeScript, Tailwind CSS), `react-leaflet`
  for the map, `recharts` for analytics charts.
- **AI providers**: DeepSeek (`deepseek-chat`) for language generation and fact
  extraction; Tavily for web search (the AI itself has no built-in browsing).

---

## 3. Data Sources & Pipeline

### 3.1 Property Price Register (PPR)
Ireland's official register of residential property sale prices, published by
the Property Services Regulatory Authority. Gives every property its **sale
history**: date of sale, price, and a short description. This is the single
most important input — it's what lets the model compute *years since last
sale*, one of the strongest available proxies for "this property is overdue
for a change of ownership."

### 3.2 Planning Permissions
National planning application register (via an ArcGIS REST feed), containing
application number, description, decision, dates, and — crucially — an
application **category**. A `Retention` application (asking for permission
*after the fact* for work already carried out) is a strong, well-documented
precursor to a sale, because buyers' solicitors require clean planning
compliance before a sale can close.

*(Note: the source feed itself truncates `DevelopmentDescription` to 80
characters — this is a limitation of the public register, not of this
application.)*

### 3.3 Daft.ie Listings (historical)
A large scraped archive of Ireland's largest property portal, giving rich
per-address history: every time a property was listed for sale/rent, at what
price, whether it later sold, BER rating, etc. This is what allows detection
of **re-listing patterns**, **price drops**, and **rent → sale transitions**.

### 3.4 Derelict / Vacant Sites Registers
Several local authorities (Dún Laoghaire-Rathdown, South Dublin, Fingal,
Roscommon, Cork City, Dublin City) publish public registers of derelict or
vacant properties (Derelict Sites Act 1990 / Vacant Sites Register). Being on
one of these registers is one of the strongest signals available — these are
properties local government has already flagged as underused, and are often
subject to a levy that pressures owners toward sale or redevelopment.

**Deliberately excluded everywhere**: owner/occupier name fields, applicant
name fields, and any other personal data present in the source registers.
Only property/site-level facts are ever downloaded or stored (see [Section
11](#11-privacy--gdpr-design-principles)).

### 3.5 Pipeline Pattern
Every source follows the same repeatable pattern:

```
download_<source>.py        → raw CSV/JSON from the public API
prepare_<source>_csv.py     → cleaned, normalized CSV (encoding fixes,
                               column renames, ITM→WGS84 coordinates)
psql \copy                  → bulk-load into a *_staging table
SQL migration (0N_*.sql)    → INSERT ... SELECT into production tables,
                               deduping / matching by address, eircode,
                               or spatial proximity (ST_DWithin)
```

---

## 4. Database Design

Core tables (all in PostgreSQL + PostGIS):

| Table | Purpose |
|---|---|
| `properties` | One row per known property: address, eircode, GPS location, and the **materialized** `propensity_score` / `key_drivers` |
| `sales_history` | PPR sale records linked to a property |
| `planning_permissions` | Planning applications linked to a property |
| `derelict_sites` | Derelict/vacant register entries linked to a property |
| `daft_listings` | Daft.ie listing history linked to a property |
| `ai_research_findings` | Cached results of AI-driven web research per property |

Supporting views:

| View | Purpose |
|---|---|
| `property_propensity_signals` | Raw, per-property signal aggregation (years since sale, has retention, is derelict, Daft signals) |
| `property_propensity_score_v2` | Final percentile-based score + key drivers (see Section 5) |
| `daft_property_signals_scored` | Relisting count, price-drop %, rent→sale detection from Daft history |
| `properties_map` | Lightweight lat/lng projection of `properties`, for the map |

**Why scores are materialized, not computed live**: with ~988,000 properties,
computing the score on every API request (via a live view with correlated
subqueries) hit PostgREST's statement timeout. Scores are computed once via a
SQL migration and written directly onto the `properties` row, so the API only
ever does a simple indexed `SELECT`.

---

## 5. The Propensity Score Algorithm

### 5.1 Version 1 — Additive Point Scoring (deprecated)

The original design simply summed weighted points per signal, capped at 100:

```
score = LEAST(100,
    LEAST(years_since_last_sale / 15, 1) * 30      -- up to 30 pts
  + (25 if retention permission else 5 if any permission else 0)
  + (30 if on derelict/vacant register else 0)
  + (15 if previously rented, now for sale else 0)
  + (10 if relisted more than twice else 0)
  + (10 if asking price dropped more than 5% else 0)
)
```

**Problem found in production**: strong signals almost never co-occur on the
same property. The real observed distribution had an average score of only
**19/100**, a maximum of **55/100**, and a near-empty band between 40 and 50
(only 59 properties out of ~988,000). The score was technically correct but
**not realistically differentiated** — it didn't spread properties out across
the full risk spectrum the way a usable ranking tool needs to.

### 5.2 Version 2 — Percentile-Rank Scoring (current)

The fix: keep exactly the same underlying signals and point weights (they are
still a well-reasoned, explainable heuristic), but stop treating the raw sum
as the final answer. Instead, use it purely to **rank every property against
the entire national population**, using SQL's `PERCENT_RANK()` window
function:

```sql
raw_score = <same additive formula as v1, uncapped>

percentile_score = PERCENT_RANK() OVER (ORDER BY raw_score) * 100
```

This is the standard technique used in lead-scoring / propensity-modelling
systems: the *absolute* number of points a property racks up matters less
than *how it compares to every other property in the country*. A property in
the top 3% of raw scores should read as ~97, regardless of whether the
theoretical maximum was ever actually reachable.

**Result after rebalancing:**

| Metric | v1 (additive) | v2 (percentile) |
|---|---|---|
| Average score | 19.2 | 46.0 |
| Median score | 18.0 | 47.9 |
| Max score observed | 55.0 | 97.4 |
| Score spread | Clustered 0–55 | Full 0–100 range |

### 5.3 Adding the AI Research Bonus

The percentile score leaves headroom (it never reaches exactly 100 by
design), which is intentionally used as space for the **AI research layer**
(Section 8) to add real, individually-verified evidence:

```
final_propensity_score = LEAST(100, percentile_score + ai_signal_score)
```

Where `ai_signal_score` is a 0–20 point bonus assigned by DeepSeek *only*
when it finds genuine, address-specific public evidence (e.g. an active
"for sale" listing found in the wild that isn't yet in the Daft dataset).
This score is 0 by default and only changes when a user actually triggers a
web-research pass for that property (see Section 8).

### 5.4 Performance Note

Because `PERCENT_RANK()` needs to sort the *entire* population, recomputing
it is a heavy, whole-table operation (run manually via a SQL migration, a
few minutes over ~988k rows). To let a **single property's** score update
cheaply after an AI research pass (without re-sorting the whole table), the
intermediate `percentile_score` and `base_key_drivers` are persisted as
columns on `properties`, so a one-row `UPDATE` is all that's needed.

---

## 6. Risk Factors ("Key Drivers") Explained

Each of the six signals below corresponds to one human-readable sentence
shown in the UI, so a user always sees *why* a property scored the way it
did:

| Signal | Points (raw) | UI text example |
|---|---|---|
| Years since last recorded sale (capped at 15 yrs) | up to 30 | "18 years since last sale" |
| Retention planning application | 25 | "Retention planning application" |
| Any other planning application | 5 | *(not shown as a headline driver)* |
| On a derelict/vacant sites register | 30 | "Listed on Derelict/Vacant Sites Register" |
| Previously rented, now listed for sale | 15 | "Previously rented, now for sale" |
| Relisted for sale more than twice | 10 | "Relisted for sale 4x" |
| Asking price cut by more than 5% | 10 | "Asking price reduced by 12%" |
| *(new)* AI-verified public finding | 0–20 | Free text, only shown if it actually raised the score |

A property with **no drivers at all** simply scores near the bottom of the
percentile range — the model never invents a reason where none exists.

---

## 7. AI Layer #1 — Natural-Language Explanation

Endpoint: `GET /properties/{id}/explain`

Once a score and its key drivers are computed (by SQL, not by AI), DeepSeek is
used **only as a language layer**: it is given the address, the score, and
the exact list of key drivers, and asked to write one short, plain-English
paragraph explaining the result.

Explicit constraint in the prompt: *"Stick to the facts in the signal list —
do not make anything up."* DeepSeek never sees raw source data and never
computes a number — it only rephrases numbers/facts that were already
computed deterministically in SQL. This keeps the score itself fully
auditable and reproducible, while still giving a non-technical user a
readable summary instead of a bare list of codes.

---

## 8. AI Layer #2 — Live Web Research

Endpoint: `POST /properties/{id}/research?force=false`

This is the newest and most powerful layer: instead of relying only on the
datasets already ingested, the platform can ask AI to actively **search the
public web right now** for anything relevant to one specific address.

**Pipeline:**

1. **Tavily search API** — a web-search API designed for AI agents — is
   queried with the property's exact address plus context keywords
   (`for sale`, `planning`, `news`, `auction`). DeepSeek itself cannot browse
   the internet, so this external search step is required.
2. **DeepSeek fact-extraction** — the raw search results (titles, URLs,
   snippets) are passed to DeepSeek with strict extraction rules:
   - Be conservative: many Irish addresses/townland names repeat across
     counties, so a result must be *clearly* about this exact property, not
     merely the general area.
   - **Never include a person's name** (owner, tenant, applicant), even if
     one appears in the source text — refer only to "the property"/"the
     owner" generically, or omit the detail entirely.
   - Return a strict JSON object: a one-sentence factual finding (or
     `null`), a `score_impact` integer from 0–20, and the source URL.
3. **Caching** — the result is written to `ai_research_findings` and to
   `properties.ai_signal_score` / `ai_signal_note` /
   `ai_signal_researched_at`. A **30-day TTL** means the same property is not
   re-searched (and doesn't re-spend Tavily/DeepSeek quota) on every page
   view — a repeat visit within 30 days just returns the cached result
   (`"cached": true` in the API response).
4. **Score update** — if (and only if) a genuine finding with
   `score_impact > 0` was found, it is appended to the property's
   `key_drivers` and folded into `propensity_score` (Section 5.3). Findings
   with zero impact (e.g. "no evidence of an imminent sale was found") are
   still stored and shown to the user for transparency, but are **not**
   listed as a driver of a high score.

This design turns the platform from a purely static/batch model into one
that can be refreshed for any individual property on demand, without needing
to re-run the entire national data pipeline.

---

## 9. API Reference

All endpoints are served by the FastAPI backend (`backend/main.py`).

| Method & Path | Description |
|---|---|
| `GET /properties/top?limit=` | Top N properties by propensity score |
| `GET /properties/map?limit=&min_score=` | Properties with GPS coordinates, for the map |
| `GET /properties?q=&min_score=&page=&page_size=` | Search/paginate by address or Eircode |
| `GET /properties/{id}` | Basic property record (address, score, key drivers) |
| `GET /properties/{id}/history` | Combined timeline: sales, planning, derelict-register, Daft listings |
| `GET /properties/{id}/explain` | AI-generated plain-English explanation of the score |
| `POST /properties/{id}/research?force=` | Trigger (or read cached) live AI web research |
| `GET /analytics/summary` | Pre-computed dashboard statistics (score distribution, totals) |
| `GET /health` | Service health + which AI features are currently enabled |

---

## 10. Frontend Application

Built with Next.js (App Router) + TypeScript + Tailwind CSS:

- **Dashboard (`/`)** — key statistics, an interactive Leaflet map of all
  scored properties (colour-coded by score), and headline data-source counts.
- **Properties (`/properties`)** — debounced search by address/Eircode, a
  minimum-score filter, and a paginated table.
- **Property Detail (`/properties/{id}`)** — three tabs:
  - *Overview*: score badge + key drivers list
  - *History*: full timeline across all four data sources
  - *AI Explanation*: DeepSeek's natural-language summary, plus the "Live Web
    Research" panel (Section 8) with a manual "Search the web for this
    property" button
- **Analytics (`/analytics`)** — score-distribution bar chart and
  data-source-mix pie chart (Recharts), computed from the materialized
  `analytics_summary` snapshot table.

The UI is responsive (a collapsible sidebar with a mobile hamburger menu) and
entirely in English.

---

## 11. Privacy & GDPR Design Principles

This is a foundational, non-negotiable design constraint that shaped every
data-ingestion decision in the project:

- **Purpose limitation**: the platform predicts *property* behaviour, never
  targets a named *individual*. All modelling happens at the address level.
- **No personal data ingested**: wherever a public register includes
  Owner/Occupier/Applicant name or address-of-owner fields (several county
  council derelict-site registers do), those fields are explicitly excluded
  at the point of download — they are never requested, stored, or passed to
  any AI model.
- **AI is instructed the same way**: both AI layers (Sections 7 & 8) carry
  explicit prompt-level instructions never to surface a person's name, even
  if one is present in an upstream source (e.g. a news article about the
  property).
- **"Public" does not mean "unprotected"**: publishing a register publicly
  does not license unrelated re-use of the personal data within it for
  profiling a named individual — this reasoning follows the same purpose
  limitation logic applied by EU data-protection authorities in cases such
  as Clearview AI.
- **Rationale, in short**: identifying that *a property* may come to market
  soon is legitimate market-research-style analysis of public administrative
  facts; identifying *which specific person* owns it and building a profile
  of them is not, and was deliberately never built.

---

## 12. Known Limitations & Roadmap

- **Heuristic, not machine-learned**: the score is an explainable, hand-
  weighted model, not a model trained on historical "did this property
  actually sell" outcomes. A natural next step would be backtesting against
  realized sales to calibrate weights statistically.
- **BER (Building Energy Rating) register is not usable at address level**:
  SEAI's public bulk BER download is anonymized (county-level only); reliable
  BER-per-address data currently comes only from the scraped Daft archive.
- **Percentile scoring produces a "staircase" pattern**: because the
  underlying signals are mostly discrete/boolean, many properties share the
  exact same raw score and therefore the exact same percentile — visible as
  a few large score plateaus rather than a perfectly smooth curve. The AI
  research layer (Section 8) is one way to break these ties with
  property-specific evidence over time.
- **AI web research runs on-demand, not on a schedule**: given Tavily's free
  tier quota, an "always keep every property fresh" batch job over ~988,000
  properties is not practical; instead, research is cached per property and
  refreshed lazily (30-day TTL) whenever a user actually views it.
- **Cadastral parcel boundaries (Tailte Éireann open data)** were evaluated
  as a possible enrichment source but rejected for now — the public dataset
  contains only county name and parcel geometry, with no address, Eircode,
  or folio number, so it would not currently improve address-matching or
  add new scoring signals.
- **Eircode coverage is partial**: full national Eircode/address data
  (GeoDirectory) is a commercial product with restrictive licensing; Eircode
  coverage today comes opportunistically from Daft listing titles and newer
  PPR records plus geocoding, not a complete national mapping.
