# Setup

## 1. Install

Install [uv](https://docs.astral.sh/uv/), then:

```bash
git clone <this repo>
cd cycling-social-agent
uv sync
```

## 2. Strava

1. Create an API application at <https://www.strava.com/settings/api>. Note your `Client ID` and `Client Secret`.
2. Authorise with scope `read,activity:read_all` — the agent reads the activity's private `description` as the "feeling" note, so `activity:read` alone is **not enough**. Open this URL in a browser (replace `CLIENT_ID`):

   ```
   https://www.strava.com/oauth/authorize?client_id=CLIENT_ID&response_type=code&redirect_uri=http://localhost/exchange_token&approval_prompt=force&scope=read,activity:read_all
   ```

   `approval_prompt=force` is important — without it, Strava silently re-uses any prior consent and you'll get a token with the old scope. After authorising, Strava redirects to `http://localhost/exchange_token?code=<CODE>&scope=read,activity:read_all`. Verify `activity:read_all` is in the returned `scope` before proceeding.

3. Exchange the code for a refresh token:

   ```bash
   curl -X POST https://www.strava.com/api/v3/oauth/token \
     -F client_id=<CLIENT_ID> \
     -F client_secret=<CLIENT_SECRET> \
     -F code=<CODE> \
     -F grant_type=authorization_code
   ```

4. Confirm you can refresh: `curl -X POST https://www.strava.com/api/v3/oauth/token -F client_id=... -F client_secret=... -F grant_type=refresh_token -F refresh_token=...`.

Put `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN`, and `STRAVA_ATHLETE_ID` in `.env`.

> If the agent logs `Authorization Error ... 'field': 'activity:read_permission', 'code': 'missing'`, your refresh token was minted with insufficient scope. Redo step 2 with `approval_prompt=force`.

## 3. Meta (Facebook + Instagram)

1. Convert the Instagram account to **Business** or **Creator** and link it to a **Facebook Page**.
2. Create a Meta App at <https://developers.facebook.com/apps/>. Add the **Facebook Login** and **Instagram Graph API** products.
3. Request the following permissions: `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`. Going through Meta App Review is required for production posting.
4. Generate a long-lived Page Access Token: short-lived → User token → exchange for long-lived → derive Page token. Meta's documentation has the exact flow.
5. Find your `META_PAGE_ID` (Page > About) and `META_IG_BUSINESS_ID` (Graph API explorer: `me/accounts` then `{page-id}?fields=instagram_business_account`).

Put `META_APP_ID`, `META_APP_SECRET`, `META_PAGE_ACCESS_TOKEN`, `META_PAGE_ID`, `META_IG_BUSINESS_ID` in `.env`.

## 4. Telegram

1. Talk to [@BotFather](https://t.me/botfather) and create a bot. Save the token.
2. Send any message to your new bot.
3. Find your chat id by visiting `https://api.telegram.org/bot<TOKEN>/getUpdates` and reading the `chat.id` field.

Put `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`.

## 5. Anthropic

Get an API key from <https://console.anthropic.com/>. Put `ANTHROPIC_API_KEY` in `.env`.

## 5a. LangSmith (optional observability)

LangChain, LangGraph, and the `deepagents` orchestrator all auto-trace to LangSmith when these vars are set. No code change required — `load_dotenv()` at startup makes them visible to the langsmith SDK.

1. Sign in at <https://smith.langchain.com/> and create an API key.
2. Set in `.env`:

   ```
   LANGSMITH_TRACING=true
   LANGSMITH_PROJECT=cycling-social-agent
   LANGSMITH_API_KEY=<your key>
   ```

Traces appear under the `cycling-social-agent` project. To disable, set `LANGSMITH_TRACING=false` (the SDK becomes a no-op — no network calls).

## 6. Seed your sponsors and style examples

```bash
cp data/sponsors.yaml.example data/sponsors.yaml
$EDITOR data/sponsors.yaml

cp data/style_examples_pt.md.example data/style_examples_pt.md
$EDITOR data/style_examples_pt.md

uv run cycling-agent init-db
uv run cycling-agent seed-sponsors
uv run cycling-agent seed-style --lang pt --path data/style_examples_pt.md
```

## 7. First run (dry-run)

```bash
uv run cycling-agent serve --dry-run
```

In Telegram, send `/start` to your bot. Tag a Strava activity as a Race. Wait for the next poll cycle (default 10 min, or set `POLL_INTERVAL_SECONDS=60` in `.env` for testing). You should receive draft cards.

## 8. Going live

When you trust the loop:

```bash
DRY_RUN=false uv run cycling-agent serve
```

Schedule it to run automatically with your platform's tools (e.g., `systemd --user`, `launchd`, or `tmux`/`screen` for foreground).

## Migration to Raspberry Pi (post-v1)

Same code, same DB; copy `.env` and the `data/` directory; install uv; add a `systemd` unit:

```ini
[Unit]
Description=cycling-social-agent
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/pi/cycling-social-agent
ExecStart=/home/pi/.local/bin/uv run cycling-agent serve
Restart=on-failure

[Install]
WantedBy=default.target
```
