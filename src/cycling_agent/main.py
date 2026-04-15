"""Application entry point.

``serve_async`` builds all components from ``Settings`` and runs the Telegram
bot + agent runner concurrently until SIGINT/SIGTERM. ``serve`` is the
sync click-friendly wrapper.
"""

from __future__ import annotations

import asyncio
import signal
from pathlib import Path

import structlog
from telegram.ext import Application

from cycling_agent.agent.orchestrator import OrchestratorDeps, build_orchestrator
from cycling_agent.agent.runner import AgentRunner
from cycling_agent.approval.bot import ApprovalBot
from cycling_agent.config import Settings, load_settings
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.models import Platform
from cycling_agent.db.repo import Repository
from cycling_agent.logging import configure_logging
from cycling_agent.publishers.base import Publisher
from cycling_agent.publishers.facebook import FacebookPublisher
from cycling_agent.publishers.instagram import InstagramPublisher
from cycling_agent.strava.client import StravaClient
from cycling_agent.strava.poller import StravaPoller

log = structlog.get_logger(__name__)


def build_repo(settings: Settings) -> Repository:
    engine = build_engine(settings.db_path)
    init_schema(engine)
    return Repository(build_session_factory(engine))


def build_strava(settings: Settings) -> StravaClient:
    return StravaClient(
        client_id=settings.strava_client_id or None,
        client_secret=settings.strava_client_secret or None,
        refresh_token=settings.strava_refresh_token or None,
    )


def build_publishers(settings: Settings) -> dict[Platform, Publisher]:
    """Build platform publishers. Real API objects are constructed lazily."""
    if settings.dry_run:
        return {
            Platform.FACEBOOK: FacebookPublisher(page=None, ig_business_id=None, dry_run=True),
            Platform.INSTAGRAM: InstagramPublisher(page=None, ig=None, dry_run=True),
        }

    from facebook_business.adobjects.iguser import IGUser
    from facebook_business.adobjects.page import Page
    from facebook_business.api import FacebookAdsApi

    FacebookAdsApi.init(
        app_id=settings.meta_app_id,
        app_secret=settings.meta_app_secret,
        access_token=settings.meta_page_access_token,
    )
    page = Page(settings.meta_page_id)
    ig = IGUser(settings.meta_ig_business_id)

    return {
        Platform.FACEBOOK: FacebookPublisher(page=page, ig_business_id=settings.meta_ig_business_id, dry_run=False),
        Platform.INSTAGRAM: InstagramPublisher(page=page, ig=ig, dry_run=False),
    }


async def serve_async(settings: Settings) -> None:
    configure_logging(settings.log_level)
    log.info("startup", dry_run=settings.dry_run, db=settings.db_path)

    repo = build_repo(settings)
    strava = build_strava(settings)
    poller = StravaPoller(client=strava, repo=repo)
    publishers = build_publishers(settings)

    application = Application.builder().token(settings.telegram_bot_token).build()
    chat_id = int(settings.telegram_chat_id) if settings.telegram_chat_id else 0
    bot = ApprovalBot(repo=repo, chat_id=chat_id)
    bot.register_handlers(application)

    deps = OrchestratorDeps(
        repo=repo,
        strava_client=strava,
        strava_poller=poller,
        publishers=publishers,
        approval_bot=bot,
        media_dir=Path("data/media"),
        publish_time_local=settings.publish_time_local,
        publish_timezone=settings.publish_timezone,
        orchestrator_model=settings.orchestrator_model,
        drafter_model=settings.drafter_model,
    )
    orchestrator = build_orchestrator(deps)
    runner = AgentRunner(
        orchestrator=orchestrator,
        repo=repo,
        interval_seconds=settings.poll_interval_seconds,
        approval_bot=bot,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    log.info("telegram_bot.started")

    try:
        await runner.run_forever(stop_event=stop_event)
    finally:
        log.info("shutdown.begin")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        log.info("shutdown.complete")


def serve() -> None:
    """Sync entry point used by the click ``serve`` command."""
    settings = load_settings()
    asyncio.run(serve_async(settings))
