# Cycling Social Agent — Design Spec

- **Date:** 2026-04-15
- **Status:** Approved (brainstorming)
- **Owner:** Sandro Rodrigues
- **Repo:** `~/work/personal/cycling-social-agent/` (standalone)

## 1. Summary

A personal automation agent that watches a pro cyclist's Strava account for race activities and produces approval-gated social media posts on Facebook and Instagram. Posts mix technical race data with the rider's first-person voice, always credit sponsors, and are reviewed via a Telegram bot before publication.

The agent is implemented as a **DeepAgents** orchestrator (LangChain ecosystem) running locally on the rider's laptop. State is persisted in SQLite so that sleep/wake cycles and multi-hour approval delays do not lose work.

## 2. Goals

- Detect new race activities on Strava automatically (no manual trigger).
- Generate platform-tailored draft posts in Portuguese and English for Facebook Page and Instagram Business.
- Always include the configured sponsors in every post.
- Capture the rider's voice via few-shot examples plus a per-race "feeling" note pulled from the Strava activity's private description.
- Require explicit human approval (with edit / regenerate / reject options) before any post is published.
- Be robust to laptop sleep, intermittent connectivity, and approvals that take hours.

## 3. Non-goals (v1)

- Auto-publishing without human approval.
- Stories, Reels, Twitter/X, LinkedIn, Threads, Bluesky.
- Sponsor tiers, rotation, or contractual logic — flat sponsor list, all mentioned every time.
- Retroactive posts for races prior to install date.
- Multi-rider / team support.
- Web dashboard or admin UI beyond the Telegram bot and CLI.
- Hosted deployment (VPS, cloud). Laptop-only for v1.

## 4. Architectural decisions

### 4.1 Top-level orchestration: DeepAgents (not a fixed LangGraph workflow)

The orchestrator is a single deep agent invoked once per scheduler tick. It uses a planning tool, a set of tools, and one type of sub-agent. It decides each cycle which races to process and in what order, bounded by tool-enforced invariants and a per-cycle scope cap.

**Rationale:** the workflow has a creative core (drafting) and a small but real amount of state-dependent reasoning (which drafts still need work, how to handle a rejection, when to give up and alert). A deep-agent loop expresses this naturally with less glue code than a state graph, while sub-agents give clean isolated contexts for each draft.

**Trade-off accepted:** higher LLM cost than a deterministic workflow, mitigated by a cheap model for orchestration, a per-cycle scope cap, and a smart-but-bounded model for drafting.

### 4.2 Approval as DB state machine, not blocking await

`send_for_approval` does not await the user. It posts to Telegram and writes the draft as `awaiting_approval` in SQLite with the Telegram message ID. The bot writes the user's response back to SQLite. Subsequent agent cycles read the state and act.

**Rationale:** the laptop will sleep. A blocking `await` across hours of sleep is fragile. A DB-mediated handoff is laptop-sleep-safe, lets multiple drafts be in flight, and keeps the bot and agent processes loosely coupled.

### 4.3 Drafting as a per-(platform, language) sub-agent

Each draft is produced by a fresh drafter sub-agent invocation with isolated context: activity summary, feeling text, sponsors, language-specific style examples, platform constraints. Returns the final caption + suggested hashtags.

**Rationale:** clean context per draft prevents cross-contamination (e.g., the FB long-form draft leaking into the IG short-form draft). Sub-agents internally do draft → self-critique → refine, which is where deep-agent shape earns its keep over a single LLM call.

### 4.4 Tools enforce invariants

Without a fixed workflow, ordering and policy are enforced by the tools themselves:

- `send_for_approval` rejects drafts missing any sponsor handle from `sponsors.yaml`.
- `publish_to_*` rejects unless the draft status in DB is `approved`.
- `mark_processed` rejects unless every (platform × language) draft for the activity is in a terminal state (`published` or `rejected`).

The agent has freedom in *what* to do but no path to violate these invariants.

## 5. Components

```
cycling-social-agent/
├── pyproject.toml                    # uv-managed; Python 3.12+
├── data/
│   ├── sponsors.yaml                 # flat list, all mentioned every post
│   ├── style_examples_pt.md          # rider's past posts, Portuguese
│   └── style_examples_en.md          # rider's past posts, English
├── docs/
│   └── superpowers/specs/            # design docs
├── src/cycling_agent/
│   ├── main.py                       # entry: scheduler + telegram bot + agent runner
│   ├── config.py                     # env + secrets
│   ├── cli.py                        # serve, init-db, seed-sponsors, test-publish, dry-run
│   ├── agent/
│   │   ├── runner.py                 # invokes the deep agent every N minutes
│   │   ├── orchestrator.py           # main DeepAgent: instructions + tools + subagents
│   │   ├── subagents/
│   │   │   └── drafter.py            # per-draft sub-agent
│   │   ├── tools/
│   │   │   ├── strava_tools.py       # list_new_races, get_activity_detail, get_feeling
│   │   │   ├── media_tools.py        # render_stats_card, render_route_map
│   │   │   ├── content_tools.py      # read_sponsors, read_style_examples
│   │   │   ├── approval_tools.py     # send_for_approval, check_approval_status
│   │   │   ├── publish_tools.py      # publish_to_facebook, publish_to_instagram
│   │   │   └── state_tools.py        # mark_processed, record_post, log_feedback
│   │   └── prompts/
│   │       ├── orchestrator.md       # standing instruction for each cycle
│   │       └── drafter.md            # how to write a draft
│   ├── strava/
│   │   ├── client.py                 # stravalib wrapper, OAuth refresh
│   │   └── poller.py                 # detects new activities with workout_type=Race
│   ├── publishers/
│   │   ├── base.py                   # Publisher protocol
│   │   ├── facebook.py               # Graph API: page feed posts with media
│   │   └── instagram.py              # Graph API: IG Business container + publish
│   ├── approval/
│   │   └── bot.py                    # python-telegram-bot; long-polling
│   ├── media/
│   │   ├── stats_card.py             # Pillow render of key stats
│   │   └── route_map.py              # decode polyline → map tile composite
│   └── db/
│       ├── models.py                 # SQLAlchemy models
│       └── repo.py                   # data access layer
└── tests/
    ├── unit/
    └── fixtures/                     # recorded Strava + Meta API responses
```

## 6. Workflow

### 6.1 Per-cycle loop (every N minutes)

A scheduler in `runner.py` invokes the orchestrator agent with the standing instruction:

> Process new race activities. Plan: (1) list_new_races; (2) for each race not yet fully published, fetch context including the "feeling" from the activity's private description; (3) for each (platform × language) combination not yet drafted, render media and spawn a drafter sub-agent; (4) call send_for_approval for new drafts; (5) call check_approval_status for any pending approvals — for each that became `approved` since last cycle, publish; (6) record state. Process at most one race per cycle. If nothing to do, exit.

The agent writes its plan as a todo list (DeepAgents planning tool), executes, exits.

### 6.2 Per-race state machine (in DB)

Activity transitions:

```
detected → drafting → awaiting_approval → processed
```

`processed` is reached only via `mark_processed`, which fires when every (platform × language) draft is in a terminal state (`published` or `rejected`). An activity can therefore end up `processed` with a mix of published and rejected drafts; per-draft outcome lives on the `drafts` table, not on the activity.

Each `(activity_id, platform, language)` draft transitions independently:

```
pending → drafted → awaiting_approval → approved → published
                                     └─► rejected
                                     └─► editing → awaiting_approval
                                     └─► regenerating → drafted
```

An activity is `processed` only when every draft is in a terminal state (`published` or `rejected`).

### 6.3 Approval UX (Telegram)

For each draft the bot sends a message containing:

- Rendered media (route map composite + stats card; optional rider photo if attached later)
- Draft caption + hashtags
- Inline buttons: ✅ Approve | ✏️ Edit | 🔄 Regenerate | ❌ Reject

Flows:

- **Approve:** bot writes `approved` to DB. Next agent cycle publishes.
- **Edit:** bot prompts for replacement caption; rider replies; bot re-renders preview; rider can approve or edit again.
- **Regenerate:** bot prompts for an optional hint (e.g., "more grateful, less hype"). Hint is logged as feedback and passed to the drafter sub-agent on retry.
- **Reject:** bot writes `rejected` to DB. No publish.
- **Photo attach:** before approval, rider can reply with one or more photos. Bot stores them and they replace the auto-generated stats card image (or augment it; rider chooses via a follow-up button).

## 7. Data model (SQLite via SQLAlchemy)

| Table | Key fields |
|---|---|
| `activities` | `id` (Strava activity id), `started_at`, `name`, `workout_type`, `feeling_text`, `status`, `created_at`, `processed_at` |
| `drafts` | `id`, `activity_id`, `platform` (`facebook`/`instagram`), `language` (`pt`/`en`), `caption`, `hashtags`, `media_paths`, `status`, `telegram_message_id`, `feedback_hint`, `regenerate_count`, `created_at`, `updated_at` |
| `posts` | `id`, `draft_id`, `platform`, `external_post_id`, `published_at` |
| `sponsors` | `id`, `name`, `handle_facebook`, `handle_instagram`, `hashtag` (loaded from `sponsors.yaml` on startup) |
| `style_examples` | `id`, `language`, `text`, `enabled` (loaded from markdown files on startup) |
| `agent_runs` | `id`, `started_at`, `finished_at`, `tool_call_count`, `cost_estimate_usd`, `outcome`, `error_text` |
| `approval_events` | `id`, `draft_id`, `event` (`approved`/`edited`/`regenerated`/`rejected`/`photo_added`), `payload`, `at` |

`approval_events` gives an audit trail and is the data source for tuning the style guide and few-shot examples over time.

## 8. External integrations

### 8.1 Strava

- **Auth:** OAuth2 with refresh token; first-run CLI flow to obtain tokens.
- **Polling:** `GET /athlete/activities` every N minutes (default 10). Filter for `type in (Ride, Run)` and `workout_type` matching race codes (Ride: `11`, Run: `1`).
- **Detail fetch:** for each candidate, `GET /activities/{id}` to read `description` (the "feeling"), `map.summary_polyline`, splits, segments, and stream stats.
- **Rate budget:** Strava API allows 100 req / 15 min and 1000 / day. At 10-min poll interval that's 144 list calls/day plus ~5–10 detail calls per race. Comfortable margin.

### 8.2 Meta (Facebook + Instagram)

- **Auth:** long-lived Page Access Token for the Facebook Page; Instagram Business account linked to the Page.
- **App permissions required:** `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`. App review may be needed depending on Meta policy at implementation time.
- **Facebook publishing:** `POST /{page-id}/photos` (single image) or `/feed` (text + media). Local file upload supported.
- **Instagram publishing:** two-step. (1) Create media container with `POST /{ig-user-id}/media` — requires `image_url` for image media. (2) Publish container with `POST /{ig-user-id}/media_publish`.
- **The IG `image_url` constraint:** Instagram cannot accept a local file directly. Three options for the laptop-only deployment:
  - **Option A:** Use Facebook's `/photos` upload (which does accept local files) to upload the image to a private FB album, then use the resulting CDN URL as `image_url` for the IG container. No external infra needed. **This is the chosen approach for v1.**
  - Option B: ngrok-style tunnel from laptop. Adds a runtime dependency.
  - Option C: small object store (Cloudflare R2 free tier). Adds an external service.

### 8.3 Telegram

- **Auth:** bot token from BotFather; rider's chat ID hardcoded in config (single-user app).
- **Mode:** long-polling. No public URL needed; works behind any NAT.
- **Library:** `python-telegram-bot` v21+.

## 9. Tools (interface contracts)

All tools are async. All state-modifying tools are idempotent w.r.t. their primary key.

| Tool | Inputs | Output | Invariant enforced |
|---|---|---|---|
| `list_new_races()` | — | list of activity ids not yet in DB or in non-terminal state | — |
| `get_activity_detail(id)` | activity id | full activity dict + feeling text | — |
| `read_sponsors()` | — | list of sponsor dicts | — |
| `read_style_examples(language)` | `pt`/`en` | list of past-post strings | — |
| `render_stats_card(activity)` | activity dict | path to PNG | — |
| `render_route_map(activity)` | activity dict | path to PNG | — |
| `send_for_approval(activity_id, platform, language, caption, hashtags, media_paths)` | as named | telegram message id | rejects if any sponsor handle missing from caption |
| `check_approval_status(draft_id)` | draft id | `pending` / `approved` / `edited(text)` / `regenerated(hint)` / `rejected` | — |
| `publish_to_facebook(draft_id)` | draft id | external post id | rejects unless draft status == `approved` |
| `publish_to_instagram(draft_id)` | draft id | external post id | rejects unless draft status == `approved` |
| `mark_processed(activity_id)` | activity id | success | rejects unless all drafts in terminal state |
| `log_feedback(draft_id, kind, payload)` | as named | success | — |

## 10. Cost model and guardrails

- **Models:** Haiku for the orchestrator (cheap planning + tool dispatch), Sonnet for the drafter sub-agent (creative work).
- **Per-cycle cap:** at most one race processed per scheduler tick. Pending races are picked up on the next tick.
- **Tool-call cap:** orchestrator capped at ~30 tool calls per cycle (DeepAgents `recursion_limit`). Hitting the cap logs a warning and sends a Telegram alert; cycle exits.
- **Idle-cycle short-circuit:** if `list_new_races` returns empty the orchestrator should exit in 1–2 LLM calls. Verified in tests.
- **Estimated cost:** sub-cent per idle cycle; ~$0.30 per race (4 drafts × drafter loop). Well below any meaningful budget for personal use.

## 11. Error handling

| Failure mode | Behavior |
|---|---|
| Strava API down or rate-limited | Skip cycle; retry on next tick; if 5 consecutive failures, Telegram alert |
| Strava token refresh fails | Telegram alert with the manual re-auth CLI command |
| Drafter sub-agent fails | Orchestrator retries once with a higher temperature; on second failure, Telegram alert with raw activity data so rider can post manually |
| `send_for_approval` invariant rejection (missing sponsor) | Orchestrator re-spawns drafter with explicit reminder; capped at 3 attempts |
| Meta publish failure (transient) | Retry 3× with exponential backoff; on final failure, Telegram alert with the approved draft text and media paths |
| Meta publish failure (permission/auth) | Telegram alert with the specific Graph API error so rider can fix in Meta Business |
| Telegram bot disconnect | python-telegram-bot auto-reconnects; missed updates are recovered via long-polling offset |
| Process crash | Next process start reads DB, finds in-flight drafts, resumes (idempotent design) |
| Laptop sleep mid-cycle | DeepAgent invocation fails; next scheduler tick on wake re-invokes from clean state — DB is the source of truth |

## 12. Testing strategy

- **Unit tests** per node, mocking Strava / Meta / LLM / Telegram at boundaries.
- **Recorded fixtures:** real Strava activity JSON for a race and a non-race ride; real Meta API response shapes for success and error cases.
- **Style regression tests:** a small set of golden race contexts with assertions on the drafter sub-agent output — length within range, all sponsors present, no banned phrases, language matches request. Use a cheap classifier prompt for the qualitative checks, with a deterministic seed.
- **Tool invariant tests:** assert each invariant-enforcing tool actually rejects bad input (missing sponsor, wrong status, etc.).
- **Dry-run mode:** `--dry-run` flag on `serve` short-circuits publishers to log instead of post; lets the rider exercise the full loop end-to-end against a real Telegram bot without risking real social posts.
- **Smoke test target:** seed the DB with a fixture race activity, run one cycle, verify (a) drafts created, (b) Telegram messages sent, (c) on simulated approval, dry-run publishers receive correctly-formed payloads.

## 13. Configuration

A single `.env` file in the project root:

```
STRAVA_CLIENT_ID=
STRAVA_CLIENT_SECRET=
STRAVA_REFRESH_TOKEN=
STRAVA_ATHLETE_ID=

META_APP_ID=
META_APP_SECRET=
META_PAGE_ACCESS_TOKEN=
META_PAGE_ID=
META_IG_BUSINESS_ID=

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

ANTHROPIC_API_KEY=

POLL_INTERVAL_SECONDS=600
ORCHESTRATOR_MODEL=claude-haiku-4-5-20251001
DRAFTER_MODEL=claude-sonnet-4-6
DB_PATH=./data/cycling.db
DRY_RUN=false
LOG_LEVEL=INFO
```

A first-run CLI command (`cycling-agent setup`) walks the rider through obtaining each token interactively and writes the file.

## 14. Open questions / followups (post-v1)

- Should approved drafts be queued and published at a configurable time-of-day (e.g., always 19:00 local for engagement), or published immediately on approval? Current design publishes immediately; can be revisited after observing engagement patterns.
- Should the agent learn from `approval_events` (edits, regenerates with hints) to refine the style guide automatically over time? Clear value, deferred until the data exists.
- Move to a Raspberry Pi or VPS for always-on operation. Trivial migration: same code, change `DB_PATH` and add a process supervisor.
- Add a simple web UI for browsing the post history and editing the style guide / sponsor list without touching files.
