"""Build the deep-agent orchestrator with all tools and sub-agents wired in."""

from __future__ import annotations

import asyncio
import dataclasses
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langchain_anthropic import ChatAnthropic

from cycling_agent.agent.prompts import load_prompt
from cycling_agent.agent.subagents.drafter import build_drafter_subagent
from cycling_agent.agent.subagents.reflector import build_reflector_subagent
from cycling_agent.agent.tools.approval_tools import build_approval_tools
from cycling_agent.agent.tools.content_tools import build_content_tools
from cycling_agent.agent.tools.media_tools import build_media_tools
from cycling_agent.agent.tools.publish_tools import build_publish_tools
from cycling_agent.agent.tools.state_tools import build_state_tools
from cycling_agent.agent.tools.strava_tools import build_strava_tools
from cycling_agent.approval.bot import ApprovalBot
from cycling_agent.db.models import Platform
from cycling_agent.db.repo import Repository
from cycling_agent.publishers.base import Publisher
from cycling_agent.strava.client import StravaClient
from cycling_agent.strava.poller import StravaPoller


@dataclasses.dataclass
class OrchestratorDeps:
    repo: Repository
    strava_client: StravaClient
    strava_poller: StravaPoller
    publishers: dict[Platform, Publisher]
    approval_bot: ApprovalBot
    media_dir: Path
    publish_time_local: str
    publish_timezone: str
    orchestrator_model: str
    drafter_model: str
    reflector_model: str
    # The application's main asyncio loop. Approval tools run in worker
    # threads (via ``asyncio.to_thread`` in the runner) and must submit
    # Telegram coroutines back to this loop — see ``build_approval_tools``.
    main_loop: asyncio.AbstractEventLoop
    # Platforms the orchestrator should generate drafts for. Usually equals
    # ``publishers.keys()`` but kept explicit so a disabled platform can be
    # paused without removing its publisher wiring.
    enabled_platforms: set[Platform] = dataclasses.field(
        default_factory=lambda: {Platform.FACEBOOK, Platform.INSTAGRAM}
    )
    # Languages to draft in. Single-language today, but kept as a parameter
    # so future multilingual rollout doesn't require touching the prompt.
    languages: tuple[str, ...] = ("pt",)


def _render_platforms_loop(platforms: set[Platform], languages: tuple[str, ...]) -> str:
    """Render the ``[(facebook, pt), (instagram, pt)]`` list the orchestrator prompt expects.

    Platforms are emitted in a stable order so the prompt is deterministic.
    """
    order = [Platform.FACEBOOK, Platform.INSTAGRAM]
    pairs = [f"({p.value}, {lang})" for p in order if p in platforms for lang in languages]
    return "[" + ", ".join(pairs) + "]"


def _collect_tools(deps: OrchestratorDeps) -> list[Any]:
    tools: list[Any] = []
    tools.extend(build_strava_tools(repo=deps.repo, client=deps.strava_client, poller=deps.strava_poller))
    tools.extend(build_content_tools(repo=deps.repo))
    tools.extend(build_media_tools(repo=deps.repo, strava=deps.strava_client, media_dir=deps.media_dir))
    tools.extend(build_approval_tools(repo=deps.repo, bot=deps.approval_bot, main_loop=deps.main_loop))
    tools.extend(
        build_publish_tools(
            repo=deps.repo,
            publishers=deps.publishers,
            publish_time_local=deps.publish_time_local,
            publish_timezone=deps.publish_timezone,
        )
    )
    tools.extend(build_state_tools(repo=deps.repo))
    return tools


def build_orchestrator(deps: OrchestratorDeps) -> Any:
    """Build the deep-agent orchestrator. Returns the runnable agent."""
    tools = _collect_tools(deps)
    system_prompt = load_prompt(
        "orchestrator",
        platforms_loop=_render_platforms_loop(deps.enabled_platforms, deps.languages),
    )
    subagents = [
        build_drafter_subagent(model=deps.drafter_model),
        build_reflector_subagent(model=deps.reflector_model),
    ]
    model = ChatAnthropic(model=deps.orchestrator_model, max_tokens=4096)

    return create_deep_agent(
        tools=tools,
        system_prompt=system_prompt,
        subagents=subagents,
        model=model,
    )
