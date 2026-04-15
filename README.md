# cycling-social-agent

Personal automation agent that turns Strava race activities into approval-gated social posts on Facebook and Instagram.

## What it does

1. Polls Strava every 10 minutes (configurable) for activities with `workout_type=Race`.
2. For each new race, generates four drafts: Facebook + Instagram, in Portuguese + English. Drafts use a per-race "feeling" note (the activity's private description in Strava) and few-shot voice examples from past posts.
3. Sends each draft to your Telegram with inline buttons: Approve (queued), Approve & post now, Edit, Regenerate, Reject.
4. Approved drafts are queued for `PUBLISH_TIME_LOCAL` (default 19:00 Lisbon time). "Approve & post now" publishes immediately.
5. All drafts must include every sponsor — the agent enforces this as a hard invariant.

See the [design spec](docs/superpowers/specs/2026-04-15-cycling-social-agent-design.md) for the full architecture.

## Setup

See [docs/setup.md](docs/setup.md).

## Daily use

```bash
# Foreground (use a terminal multiplexer):
uv run cycling-agent serve

# In dry-run (no real posts published):
uv run cycling-agent serve --dry-run

# Generate a style-guide proposal from recent edits:
uv run cycling-agent reflect

# Reload sponsors after editing data/sponsors.yaml:
uv run cycling-agent seed-sponsors

# Reload style examples after editing the markdown files:
uv run cycling-agent seed-style --lang pt --path data/style_examples_pt.md
uv run cycling-agent seed-style --lang en --path data/style_examples_en.md
```

## Development

```bash
uv run pytest -q
uv run ruff check --fix src tests
uv run ruff format src tests
uv run ty check src tests
```

## License

Personal use. No license granted.
