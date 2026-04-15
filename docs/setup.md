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
2. Use any OAuth flow (e.g., the [strava-tokens helper](https://developers.strava.com/docs/getting-started/)) to exchange your authorisation code for a refresh token.
3. Confirm with `curl -X POST https://www.strava.com/api/v3/oauth/token -F client_id=... -F client_secret=... -F grant_type=refresh_token -F refresh_token=...` that you can refresh.

Put `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `STRAVA_REFRESH_TOKEN`, and `STRAVA_ATHLETE_ID` in `.env`.

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

## 6. Seed your sponsors and style examples

```bash
cp data/sponsors.yaml.example data/sponsors.yaml
$EDITOR data/sponsors.yaml

cp data/style_examples_pt.md.example data/style_examples_pt.md
cp data/style_examples_en.md.example data/style_examples_en.md
$EDITOR data/style_examples_pt.md
$EDITOR data/style_examples_en.md

uv run cycling-agent init-db
uv run cycling-agent seed-sponsors
uv run cycling-agent seed-style --lang pt --path data/style_examples_pt.md
uv run cycling-agent seed-style --lang en --path data/style_examples_en.md
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
