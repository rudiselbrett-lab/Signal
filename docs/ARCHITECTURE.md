# Forge — System Architecture

> **Status:** Proposed — awaiting review. No application code will be written until this document is approved.
>
> Forge helps professionals turn information into lasting expertise. It is not a read-it-later app: it continuously discovers high-value content, helps users understand it, reinforces it over time, and lets them apply everything they've learned through an AI assistant grounded exclusively in their own knowledge library.

---

## 1. The Learning Loop

Every architectural decision serves this loop:

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│   Suggest ──▶ Learn ──▶ Reinforce ──▶ Apply (AI Q&A)     │
│      ▲                                      │            │
│      └───────── Improve future suggestions ◀┘            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

| Loop stage | Owning service(s) | Signal produced |
|---|---|---|
| Suggest | Discovery, Scoring, Recommendations | Which articles were surfaced, accepted, dismissed |
| Learn | Library, Knowledge Extraction, Embeddings | Read events, completion, confidence self-rating |
| Reinforce | Reinforcement Engine | Review performance (ease, recall accuracy) |
| Apply | Chat (AI Knowledge Coach) | Query topics, retrieval hits/misses (knowledge gaps) |
| Improve | Analytics → User Interest Profile | Updated interest vector + topic mastery, fed back into Scoring |

The **User Interest Profile** (§8.6) is the feedback artifact that closes the loop: a continuously updated model of what the user knows, cares about, and is weak in. Scoring reads it; every other stage writes to it.

---

## 2. High-Level System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Next.js Frontend (Vercel-style)               │
│   Dashboard · Library · Reader · Reviews · Coach Chat · Graph · Search │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │ REST + SSE (typed client, OpenAPI-generated)
┌──────────────────────────────▼─────────────────────────────────────────┐
│                        FastAPI Application (API Layer)                 │
│   Routers → Application Services → Domain → Repositories               │
│   Auth · Rate limiting · OpenAPI · SSE streaming for chat              │
└──────┬────────────────────────────────────────────────┬────────────────┘
       │                                                │ enqueue
┌──────▼──────────────────────────────┐   ┌─────────────▼───────────────┐
│        PostgreSQL 16 + pgvector     │   │        Celery Workers       │
│  Relational data · Embeddings ·     │   │  ingestion │ enrichment │   │
│  Full-text search (tsvector) ·      │◀──│  scoring   │ reviews    │   │
│  Knowledge graph (edges table)      │   │  analytics │ (Beat cron) │  │
└─────────────────────────────────────┘   └─────────────┬───────────────┘
       ▲                                                │
       │              ┌─────────────────────────────────▼───────────────┐
       │              │                 Redis                           │
       └──────────────│   Celery broker + result backend · cache ·      │
                      │   rate-limit counters                           │
                      └─────────────────────────────────────────────────┘

External providers (behind ports/adapters — each independently replaceable):
  · Anthropic Claude ......... summarization, extraction, scoring rationale,
                               reinforcement generation, coach chat
  · OpenAI Embeddings ........ text-embedding-3-large (3072-d, stored at 1536-d)
  · Content sources .......... RSS/Atom, HN, Reddit, GitHub, arXiv, YouTube,
                               generic URL scraper (one adapter per source type)
```

### 2.1 Repository layout (monorepo)

```
forge/
├── docs/
│   ├── ARCHITECTURE.md          # this document
│   └── adr/                     # architecture decision records, one per decision
├── backend/
│   ├── pyproject.toml           # uv-managed; ruff + mypy + pytest configured
│   ├── alembic/                 # migrations
│   ├── src/forge/
│   │   ├── main.py              # FastAPI app factory
│   │   ├── config.py            # pydantic-settings, single source of env config
│   │   ├── api/                 # HTTP layer only: routers, request/response DTOs
│   │   │   └── v1/              # /api/v1/... (sources, discovery, library, ...)
│   │   ├── domain/              # pure domain layer — no I/O, no framework imports
│   │   │   ├── sources/         #   entities, value objects, domain services
│   │   │   ├── content/
│   │   │   ├── scoring/
│   │   │   ├── knowledge/
│   │   │   ├── reinforcement/
│   │   │   ├── chat/
│   │   │   └── analytics/
│   │   ├── services/            # application services (use-case orchestration)
│   │   │   ├── ingestion/       #   one package per module in §8
│   │   │   ├── scoring/
│   │   │   ├── extraction/
│   │   │   ├── embeddings/
│   │   │   ├── recommendations/
│   │   │   ├── reinforcement/
│   │   │   ├── chat/
│   │   │   └── analytics/
│   │   ├── adapters/            # implementations of ports (all I/O lives here)
│   │   │   ├── llm/             #   AnthropicClient behind LLMPort
│   │   │   ├── embeddings/      #   OpenAIEmbedder behind EmbeddingPort
│   │   │   ├── sources/         #   RSSAdapter, HNAdapter, ... behind SourceAdapter
│   │   │   └── persistence/     #   SQLAlchemy repos behind repository protocols
│   │   ├── workers/             # Celery app, task definitions, beat schedule
│   │   └── events/              # in-process domain event bus (see §5.3)
│   └── tests/                   # unit / integration / e2e, mirrors src layout
├── frontend/
│   ├── package.json             # pnpm; Next.js 15 App Router, TS strict
│   ├── src/
│   │   ├── app/                 # routes: /(app)/dashboard, /library, /reader/[id],
│   │   │   │                    #   /reviews, /coach, /graph, /sources, /settings
│   │   ├── features/            # feature folders mirroring backend modules
│   │   ├── components/ui/       # shadcn/ui primitives
│   │   ├── lib/api/             # OpenAPI-generated typed client + TanStack Query hooks
│   │   └── lib/                 # keyboard shortcuts, theming, utils
│   └── tests/
├── infra/
│   ├── docker-compose.yml       # postgres+pgvector, redis, api, worker, beat, web
│   └── Dockerfile.{api,worker,web}
└── Makefile                     # dev, test, lint, migrate, seed — one-command DX
```

**Why a monorepo:** one PR can change an API contract and its consumer atomically; the OpenAPI schema generated by FastAPI drives the frontend client, so drift is caught at build time.

---

## 3. Domain-Driven Design — Bounded Contexts

Seven bounded contexts. Each owns its tables, exposes a Python service interface plus domain events, and never reaches into another context's tables.

| Context | Responsibility | Core aggregates |
|---|---|---|
| **Sources** | What to learn from | `Source`, `Category` |
| **Content** | Discovery, ingestion, the library | `Article`, `DiscoveryRun` |
| **Scoring** | Explainable learning value | `ArticleScore` |
| **Knowledge** | Extraction, embeddings, graph | `KnowledgeCard`, `Entity`, `GraphEdge` |
| **Reinforcement** | Spaced repetition | `ReviewItem`, `ReviewSession` |
| **Coach** | Grounded RAG chat | `Conversation`, `Message`, `Citation` |
| **Analytics** | Interest profile, dashboard, streaks | `InterestProfile`, `DailyStat` |

Contexts communicate through **domain events** (§5.3) and read-only service interfaces — never via shared table access. This is what makes each module independently replaceable: swapping the Reinforcement engine for a different algorithm touches one package and zero others.

---

## 4. Tech Stack (confirmed)

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js 15 (App Router), TypeScript strict, Tailwind CSS 4, shadcn/ui | Server Components for read-heavy pages, client components for interactive surfaces |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2 | uv for dependency management |
| Database | PostgreSQL 16 + pgvector | Single database; contexts separated by schema conventions, not microservices |
| Jobs | Celery 5 + Redis broker, Celery Beat for schedules | Dedicated queues per workload (§10) |
| LLM | Anthropic Claude — Sonnet for pipeline tasks, strongest available model for the Coach | All calls behind `LLMPort` |
| Embeddings | OpenAI `text-embedding-3-large`, `dimensions=1536` | §7.2 explains the dimension choice |
| Search | Hybrid: pgvector HNSW (semantic) + Postgres `tsvector` (keyword), fused with RRF | §7.3 |
| Auth (MVP) | Single-user token auth, schema designed multi-user from day one | `user_id` on every table; swap in real auth later without migration pain |

**Deliberate exclusions (MVP):** no microservices (modular monolith — the module boundaries are the future service boundaries), no Kafka (Postgres + Celery suffice at this scale), no separate vector DB (pgvector keeps embeddings transactionally consistent with rows and enables SQL-joined hybrid search).

---

## 5. Backend Architecture

### 5.1 Layering (hexagonal / ports-and-adapters)

```
api/ (HTTP)  ──▶  services/ (use cases)  ──▶  domain/ (pure logic)
                        │
                        ▼
                  ports (Protocols)  ◀──  adapters/ (LLM, embeddings, DB, sources)
```

Rules, enforced by import-linter in CI:

1. `domain/` imports nothing from other layers. Pure Python: entities, value objects, domain services (e.g., the SM-2 scheduler is a pure function — trivially unit-testable).
2. `services/` orchestrate: load via repository ports, call domain logic, persist, emit events. They depend on **port Protocols**, never concrete adapters.
3. `adapters/` implement ports. All I/O (HTTP, DB, LLM APIs) lives here and only here.
4. `api/` is thin: parse/validate request → call one application service → shape response. No business logic in routers.

### 5.2 Key ports (the replaceability contract)

```python
class LLMPort(Protocol):
    async def complete(self, req: CompletionRequest) -> CompletionResponse: ...
    async def complete_structured(self, req, schema: type[BaseModel]) -> BaseModel: ...
    async def stream(self, req: CompletionRequest) -> AsyncIterator[StreamEvent]: ...

class EmbeddingPort(Protocol):
    async def embed(self, texts: list[str]) -> list[Vector]: ...

class SourceAdapter(Protocol):
    source_type: ClassVar[SourceType]
    async def fetch_new_items(self, source: Source, since: datetime) -> list[RawItem]: ...
    async def fetch_full_content(self, item: RawItem) -> FetchedContent: ...
```

Adding a source type (podcast, PDF, Readwise — every "future feature" in the roadmap) = one new `SourceAdapter` implementation registered in the adapter registry. Nothing else changes.

### 5.3 Domain events

An in-process event bus (simple pub/sub over the same transaction boundary; Celery tasks for async subscribers). Events are the seams between contexts:

```
article.discovered      → Scoring: score it
article.saved           → Extraction: enrich it → Embeddings: embed it
article.enriched        → Knowledge: update graph
article.read            → Reinforcement: generate review items
                        → Analytics: update streak + interest profile
review.completed        → Reinforcement: reschedule (SM-2 update)
                        → Analytics: update mastery/confidence
chat.retrieval_missed   → Analytics: record knowledge gap signal
suggestion.dismissed    → Analytics: negative interest signal
```

MVP implementation is deliberately simple (a registry of handlers, async ones dispatched as Celery tasks). The event names are the stable contract; the bus can later become an outbox + real broker without touching publishers or subscribers.

### 5.4 LLM usage policy

- Every LLM call site declares a named **prompt template** (versioned in-repo under `services/*/prompts/`) and a **Pydantic output schema**; structured outputs are parsed and validated, with one retry on validation failure.
- Model tiering: enrichment pipeline uses a fast/cheap Claude model; the Coach uses the strongest available. Model IDs live in config, never in code.
- All calls log tokens, latency, cost estimate, and template version (§13).
- Failures never block ingestion: an article missing enrichment is stored with `enrichment_status = failed` and retried; the pipeline is a DAG of independently retryable Celery tasks.

---

## 6. Data Model (PostgreSQL)

All tables carry `id UUID PK`, `user_id UUID`, `created_at`, `updated_at`. Names below are the significant columns only.

### 6.1 Sources context

```sql
categories       (name, color, priority_weight REAL DEFAULT 1.0)

sources          (category_id FK, name, source_type ENUM(rss, substack, blog,
                  reddit, hackernews, github, arxiv, youtube, custom_url),
                  config JSONB,            -- adapter-specific: feed URL, subreddit, repo, query…
                  enabled BOOL, priority_weight REAL DEFAULT 1.0,
                  last_checked_at, last_success_at, failure_count INT,
                  status ENUM(active, erroring, disabled))
```

### 6.2 Content context

```sql
articles         (source_id FK, url TEXT UNIQUE, canonical_url, title, author,
                  published_at, fetched_at,
                  raw_html TEXT, full_text TEXT, word_count INT,
                  reading_time_minutes INT, language,
                  content_hash TEXT,        -- dedupe across sources
                  status ENUM(discovered, suggested, saved, unread, reading,
                              learned, review_due, mastered, dismissed, archived),
                  enrichment_status ENUM(pending, enriched, failed))

discovery_runs   (started_at, finished_at, sources_checked INT, items_found INT,
                  items_scored INT, errors JSONB)   -- observability for the cron loop
```

Status lifecycle: `discovered → suggested → saved/unread → reading → learned → review_due ⇄ learned → mastered`, with `dismissed`/`archived` as exits. `review_due`/`mastered` are driven by the Reinforcement context via events — Content owns the column, Reinforcement owns the transitions.

### 6.3 Scoring context

```sql
article_scores   (article_id FK UNIQUE, overall INT,               -- 0–100
                  relevance INT, novelty INT, credibility INT, practicality INT,
                  knowledge_gap INT, reading_time_bonus INT, difficulty INT,   -- components
                  rationale JSONB,          -- per-component one-line explanations
                  scoring_version TEXT,     -- re-scorable when the model changes
                  scored_at)
```

### 6.4 Knowledge context

```sql
knowledge_cards  (article_id FK UNIQUE,
                  summary TEXT, key_ideas JSONB,          -- [{idea, quote_anchor}]
                  mental_models JSONB, frameworks JSONB,
                  topics TEXT[], tags TEXT[],
                  difficulty ENUM(intro, intermediate, advanced),
                  extraction_version TEXT)

entities         (name, kind ENUM(topic, company, product, framework, concept,
                  mental_model, person), normalized_name UNIQUE per kind,
                  description, embedding VECTOR(1536))

article_entities (article_id FK, entity_id FK, salience REAL, mentions INT)

graph_edges      (src_kind, src_id, dst_kind, dst_id,     -- article↔entity, entity↔entity
                  relation ENUM(mentions, about, related_to, contrasts_with,
                                builds_on, example_of),
                  weight REAL, evidence JSONB)             -- article_ids supporting the edge

article_chunks   (article_id FK, chunk_index INT, text TEXT, token_count INT,
                  section_path TEXT,                       -- e.g. "H2: Results > H3: Latency"
                  embedding VECTOR(1536),
                  tsv tsvector GENERATED)                  -- hybrid search unit (§7)
```

Indexes: HNSW on both `embedding` columns; GIN on `tsv`, `topics`, `tags`.

### 6.5 Reinforcement context

```sql
review_items     (article_id FK, card_type ENUM(quick_recall, multiple_choice,
                  scenario, compare, explain),
                  prompt JSONB,            -- question, options, expected key points
                  source_anchor JSONB,     -- which key idea / chunk this tests
                  -- SM-2 state:
                  ease_factor REAL DEFAULT 2.5, interval_days REAL, repetitions INT,
                  due_at TIMESTAMPTZ, lapses INT,
                  status ENUM(active, suspended, retired))

review_attempts  (review_item_id FK, session_id FK, answered_at,
                  user_answer TEXT, grade INT,             -- 0–5 (§9.3)
                  grading JSONB,                           -- LLM feedback for open-ended
                  latency_ms INT)

review_sessions  (started_at, finished_at, items_total INT, items_correct INT)
```

### 6.6 Coach context

```sql
conversations    (title, created_at, last_message_at)
messages         (conversation_id FK, role ENUM(user, assistant), content TEXT,
                  retrieval JSONB)          -- query rewrites, chunk ids, scores (auditability)
citations        (message_id FK, article_id FK, chunk_id FK, quote TEXT, ordinal INT)
```

### 6.7 Analytics context

```sql
interest_profile (user_id UNIQUE, interest_embedding VECTOR(1536),
                  topic_weights JSONB,      -- {"api-gateways": 0.82, ...} decayed over time
                  updated_at)

topic_mastery    (topic TEXT, mastery REAL, confidence REAL,     -- 0–1, from review history
                  articles_read INT, last_activity_at)

daily_stats      (date UNIQUE per user, articles_read INT, minutes_read INT,
                  reviews_done INT, reviews_correct INT, chats INT, streak_after INT)

activity_events  (kind, subject_id, metadata JSONB, occurred_at)  -- append-only event log
```

`activity_events` is the raw feed; `daily_stats`, `topic_mastery`, and `interest_profile` are projections rebuilt by the analytics worker — meaning dashboard logic can be changed and backfilled at any time.

---

## 7. Embeddings & Hybrid Search

### 7.1 Chunking

- Articles split by structure (headings, then paragraphs) into ~400–700 token chunks with 15% overlap; `section_path` preserved for citation display.
- Embedded texts are prefixed with contextual metadata (`{title} · {section_path}\n\n{chunk}`) — measurably better retrieval than bare chunks.
- Whole-article embedding = embedding of `title + summary + key ideas` (used for related-articles, dedupe, interest matching); chunk embeddings are used for chat retrieval.

### 7.2 Embedding model

`text-embedding-3-large` with `dimensions=1536`. Rationale: the model's Matryoshka training means 1536-d retains ~99% retrieval quality at half the storage/compute of 3072-d, and stays comfortably within pgvector HNSW index limits. `embedding_version` is stored so a future model swap can re-embed lazily.

### 7.3 Hybrid retrieval (used by Coach, related-articles, global search)

```
query ──▶ semantic: pgvector cosine top-50 over article_chunks
      └─▶ keyword:  websearch_to_tsquery over tsv, top-50
                     │
            Reciprocal Rank Fusion (k=60)
                     │
            filters (status, topics, date) + per-article cap (max 3 chunks)
                     │
            top-N chunks with scores → caller
```

One SQL function (`hybrid_search(query_text, query_embedding, filters)`) implements this — a single round trip, and every consumer (chat, search bar, related articles) shares the same code path. An optional LLM re-rank step is behind a config flag (off for search-as-you-type, on for Coach retrieval).

---

## 8. Service Modules

Each module = one package under `services/`, one owner-context, replaceable in isolation.

### 8.1 Content Ingestion

- **Discovery flow (Celery Beat, default every 2h + manual "Discover now"):** fan out one task per enabled source → adapter fetches new items since `last_checked_at` → normalize to `RawItem` → dedupe (URL canonicalization + `content_hash` + near-dup check via whole-article embedding cosine > 0.95) → persist as `discovered` → emit `article.discovered`.
- **Full-content fetch:** trafilatura-based extraction for HTML; per-adapter for structured sources (arXiv API, YouTube transcript API, GitHub README/releases, HN/Reddit APIs with linked-page fetch).
- **Resilience:** per-source failure counters with exponential backoff; a source erroring 5× is flagged `erroring` and surfaced in the UI, never silently dead. Per-domain rate limiting and robots.txt respect in the fetcher.

### 8.2 Scoring

Score = deterministic arithmetic over LLM-assessed and computed components. The LLM judges qualities; **code owns the weights** — so scores are stable, tunable, and explainable.

| Component | Max | How it's computed |
|---|---|---|
| Relevance | 30 | cosine(article embedding, interest embedding) blended with topic-weight overlap, scaled; source `priority_weight` multiplies |
| Novelty | 20 | inverse max-similarity vs. existing library (semantic dedupe distance) — "do I already know this?" |
| Credibility | 20 | source-type base rate + author/domain reputation + LLM assessment of evidence quality |
| Practicality | 15 | LLM: actionable takeaways vs. news/opinion |
| Knowledge Gap | 15 | overlap with topics where `topic_mastery` is low but interest is high |
| Reading Time Bonus | 5 | fits user's typical session length; long reads aren't penalized, just not bonused |
| **Overall** | **100** | sum |

Every component stores a one-line `rationale` → the UI renders the exact breakdown shown in the product spec. `scoring_version` allows re-scoring the backlog when weights change. Difficulty and reading time are computed here too (readability metrics + word count) and copied onto the article.

### 8.3 Knowledge Extraction

One structured LLM call per saved article (Pydantic-validated) producing: summary, key ideas (each anchored to a supporting quote — later used for review-item grounding and citation display), mental models, frameworks, companies, products, topics, tags, difficulty. Entities are normalized (lowercase, alias table) and upserted; `article_entities` + `graph_edges` updated in the same transaction. `extraction_version` stored for re-runs.

### 8.4 Embeddings

Listens for `article.enriched` → chunks → batch-embeds (API batching, retry with backoff) → writes `article_chunks`. Also maintains entity embeddings and the interest embedding refresh.

### 8.5 Recommendations

"Today's Suggested Reading" = top-K by score with post-processing: diversity constraint (max 2 per topic via MMR), staleness decay, at-most-one-difficult-read guardrail, and explicit exploration slot (1 of K from a low-interest topic — prevents filter-bubble collapse of the interest profile). Dismissals write negative signals.

### 8.6 Analytics & Interest Profile

Consumes `activity_events`; maintains the projections in §6.7. The **interest embedding** is an exponentially-decayed weighted mean of embeddings of: articles read (weight 1.0), saved (0.6), chat queries (0.4), dismissed (−0.5). Topic weights decay with half-life ~60 days so stale interests fade. This module is the "Improve" stage of the loop.

### 8.7 Reinforcement — see §9. 8.8 Coach — see §11 (Knowledge Graph §12).

---

## 9. Reinforcement Engine

### 9.1 Generation

On `article.read`: one structured LLM call generates 3–6 review items mixed across the five card types (quick recall, multiple choice, scenario, compare-concepts, explain-in-your-own-words). Each item is anchored to a specific key idea/quote (`source_anchor`) so questions are grounded in the article, not hallucinated. Compare-concepts items may reference a second article sharing an entity — reinforcement doubles as cross-article connection-building.

### 9.2 Scheduling — SM-2 with adaptive modifications

Base intervals match the spec (1, 3, 7, 14, 30, 90 days) as the *initial* ladder; SM-2 ease-factor adjustment then personalizes per item:

```
grade ≥ 3 (pass):  interval ← interval × ease_factor
                   ease_factor ← EF + (0.1 − (5−grade)(0.08 + (5−grade)·0.02)), min 1.3
grade < 3 (fail):  repetitions ← 0, interval ← 1 day, lapses += 1
```

Adaptations: per-user daily review cap with priority ordering (overdue > new > ahead-of-schedule); "fuzz" (±10% interval jitter) to avoid review pile-ups; item suspended after 8 lapses and surfaced as a weak-area signal instead of nagging forever. The scheduler is a **pure function** in `domain/reinforcement/` — fully unit-tested against known SM-2 vectors, replaceable by FSRS later without touching anything else.

### 9.3 Grading

- MCQ / quick recall: graded in code (0 or 5, with latency shading to 4).
- Open-ended (scenario, compare, explain): LLM grades against the item's expected key points → grade 0–5 + one-paragraph feedback ("you missed the part about…"). Grading rationale stored in `review_attempts.grading`.

Mastery: an article reaches `mastered` when all its active items have `interval ≥ 30d` and no lapses in the last 2 reviews. Aggregated per-topic into `topic_mastery` → feeds Knowledge Gap scoring and the dashboard's Weak Areas.

---

## 10. Background Jobs (Celery)

| Queue | Tasks | Why isolated |
|---|---|---|
| `ingestion` | source polling, content fetch | I/O-bound, bursty, external-failure-prone |
| `enrichment` | extraction, embeddings, scoring | LLM-rate-limited; concurrency capped to respect provider limits |
| `reviews` | review-item generation, open-ended grading | user-facing latency matters (grading is near-real-time) |
| `analytics` | projections, interest profile, graph maintenance | low priority, can lag |

Beat schedule: discovery every 2h; review-due materialization daily 05:00 (user TZ); analytics rollup hourly; interest-profile refresh daily; graph-edge consolidation weekly. All tasks are **idempotent** (keyed on natural ids) and safe to retry; enrichment is a chain of independent tasks so one failing step never loses the article.

---

## 11. AI Knowledge Coach

A chatbot that answers **only** from the user's library.

### 11.1 Pipeline (per user message)

```
1. Query understanding    Claude rewrites the message (+ conversation context) into
                          1–3 retrieval queries; classifies intent
                          (lookup / synthesis / comparison / strategy)
2. Retrieval              hybrid_search per query (§7.3) → merge → top ~12 chunks
                          (≤3 per article); comparison intent forces retrieval
                          for each comparand
3. Sufficiency gate       if best fused score < threshold → grounded refusal:
                          "Your library doesn't cover this yet" + suggested
                          sources/topics to add; emit chat.retrieval_missed
4. Answer synthesis       Claude with a strict grounding system prompt; context =
                          chunks tagged [1]..[n] with title/author/date; must cite
                          per claim; must surface disagreements between sources
                          ("Article A argues X; Article B disagrees because Y")
5. Streaming + citations  SSE token stream; citation markers resolved client-side
                          to hoverable cards linking into the reader at the chunk
6. Follow-ups             suggested next questions + related unread articles
                          ("you have 2 unread saves on this topic")
```

### 11.2 Grounding rules (system prompt contract)

- Every factual claim carries a citation to a retrieved chunk; no outside knowledge presented as fact.
- General reasoning ability (structuring an argument, applying a framework from the library to the user's stated problem) **is** allowed — that's the "Apply" stage — but premises must come from citations.
- Disagreements between sources are surfaced, not averaged away.
- Strategy prompts ("how would my reading suggest solving X?") use intent-specific prompting: retrieve frameworks/mental models, apply them explicitly, cite where each came from.

`messages.retrieval` stores the full retrieval trace for every answer — auditability and offline quality evaluation.

---

## 12. Knowledge Graph

- **Build:** nodes = articles + entities (already produced by extraction); edges = `mentions/about` (article↔entity, from extraction), `related_to` (entity↔entity via embedding similarity + co-occurrence lift), `contrasts_with`/`builds_on` (LLM-detected during extraction when an article engages another known entity's ideas). Weekly consolidation task merges duplicate entities and prunes weak edges.
- **API:** `GET /graph?focus=<node>&depth=2&kinds=…` returns a bounded subgraph (max ~150 nodes, weight-ranked) — never the whole graph.
- **UI:** interactive canvas (react-force-graph / d3-force): pan/zoom, node sizing by connectivity, coloring by kind, click → side panel with entity summary + linked articles, double-click → refocus. Entry points: global nav, and "view in graph" from any article/entity.

---

## 13. Cross-Cutting Concerns

- **Config:** pydantic-settings; one `.env.example`; fail-fast validation at boot.
- **Observability:** structlog JSON logs with request/task correlation ids; an `llm_calls` log table (template version, model, tokens, cost, latency) — LLM spend is a first-class metric on day one. Sentry-compatible error hooks.
- **Error handling:** RFC 9457 problem-details responses; typed domain exceptions mapped centrally; Celery dead-letter handling with UI surfacing for permanently failed enrichment.
- **Security:** secrets only via env; SSRF guard on user-supplied URLs (deny private IP ranges, resolve-then-connect pinning); sanitized HTML rendering in the reader; rate limits on LLM-backed endpoints.
- **Testing:** domain layer = pure unit tests (scheduler, scoring arithmetic, RRF); services tested against fake ports; adapters tested with recorded fixtures (VCR-style) + testcontainers Postgres for repository/search tests; one happy-path e2e per feature via API; frontend component tests + Playwright smoke for the reader/review/chat flows. Golden-set retrieval tests guard hybrid-search quality regressions.
- **CI:** ruff, mypy (strict), import-linter (layer rules), pytest, pnpm typecheck/lint/test, docker build.

---

## 14. Frontend Architecture

- **Routes:** `/dashboard`, `/library` (filterable table + saved views), `/reader/[articleId]` (clean reading surface: score breakdown panel, knowledge card, mark-as-read → triggers reinforcement), `/reviews` (session player, one card at a time), `/coach` (chat with streaming + citation hovers), `/graph`, `/sources`, `/settings`.
- **State:** TanStack Query for all server state (the OpenAPI-generated client gives end-to-end types); Zustand only for UI state (command palette, reader prefs). SSE for chat streaming and discovery-run progress.
- **AI-first UX (Linear + Notion + ChatGPT):**
  - `⌘K` command palette = global search (hybrid search over everything) + action launcher ("start review session", "discover now", "add source").
  - Keyboard-first: `j/k` navigate, `Enter` open, `r` start reviews, `c` open coach, `s` save, `d` dismiss, `?` shortcut overlay.
  - Dark mode default (class-based theming, system-aware), light mode supported.
  - Optimistic updates on all lightweight mutations; skeletons everywhere; sub-100ms perceived interactions.
  - Minimal chrome: single sidebar, content-focused layouts, shadcn/ui + Tailwind design tokens.

---

## 15. Implementation Roadmap

One feature per phase; each phase lands as a reviewable PR with tests, ending in a working vertical slice.

| Phase | Deliverable | Proves |
|---|---|---|
| 0 | Skeleton: monorepo scaffold, docker-compose (pg+pgvector, redis), FastAPI app factory, Next.js shell, CI, migrations, Makefile | dev experience, layering rules enforced |
| 1 | **Sources**: CRUD, categories, weights, enable/disable; RSS + custom-URL adapters first | ports/adapters pattern end-to-end |
| 2 | **Ingestion**: discovery pipeline, dedupe, full-text fetch; remaining adapters (HN, Reddit, GitHub, arXiv, YouTube) incrementally | Celery pipeline, resilience |
| 3 | **Scoring**: components, explainable breakdown UI, suggested queue | LLM structured outputs, event chain |
| 4 | **Library + Reader**: extraction, knowledge cards, statuses, library UI | the core reading experience |
| 5 | **Embeddings + Hybrid search**: chunks, HNSW, `hybrid_search()`, ⌘K global search | retrieval foundation |
| 6 | **Reinforcement**: item generation, SM-2 scheduler, review player, LLM grading | the learning loop's retention leg |
| 7 | **Coach**: full RAG pipeline, streaming, citations, refusal path | the "Apply" stage |
| 8 | **Knowledge graph**: edges, subgraph API, interactive canvas | connection-building |
| 9 | **Dashboard + Analytics**: interest profile, streaks, mastery, weak areas; recommendations diversity | the loop closes |
| 10 | Polish: keyboard shortcuts everywhere, dark-mode QA, performance pass, seed data | launch-ready feel |

Dependencies are strictly forward — each phase builds only on earlier ones.

---

## 16. Future-Feature Fit (why this architecture extends cleanly)

| Future feature | Extension point (no redesign) |
|---|---|
| Podcast / PDF / book ingestion | new `SourceAdapter` + a transcription/parsing step in the ingestion DAG |
| Personal notes, highlights, Readwise/Kindle | new `annotations` table in Knowledge context; Readwise is another adapter |
| Obsidian export / email digest / weekly report | read-only consumers of existing projections; digest = one Beat task + template |
| Slack integration | Coach pipeline already transport-agnostic; add a Slack adapter on top of the chat service |
| Team spaces / enterprise | every table already carries `user_id`; add `workspace_id` + row-level security; auth port swaps to SSO |

---

## 17. Decisions to Confirm in Review

1. **Modular monolith over microservices** for MVP (module seams preserved for later extraction) — agreed?
2. **pgvector at 1536-d** (halved via Matryoshka) rather than 3072-d or an external vector DB — agreed?
3. **Single-user MVP** with multi-user-ready schema (no login UI in phase 0–10) — agreed?
4. **SM-2 (+ adaptations)** as the initial scheduler, FSRS as a possible later swap — agreed?
5. **Score weights** as specified in §8.2 (mirroring the product spec's 30/20/20/15/15/5 split) — agreed?
6. Discovery cadence default **every 2 hours** — agreed?
