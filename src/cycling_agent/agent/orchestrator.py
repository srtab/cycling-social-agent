"""Build the deep-agent orchestrator with all tools and sub-agents wired in."""

from __future__ import annotations

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


def _collect_tools(deps: OrchestratorDeps) -> list[Any]:
    tools: list[Any] = []
    tools.extend(build_strava_tools(repo=deps.repo, client=deps.strava_client, poller=deps.strava_poller))
    tools.extend(build_content_tools(repo=deps.repo))
    tools.extend(build_media_tools(repo=deps.repo, strava=deps.strava_client, media_dir=deps.media_dir))
    tools.extend(build_approval_tools(repo=deps.repo, bot=deps.approval_bot))
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
    instructions = load_prompt("orchestrator")
    subagents = [build_drafter_subagent(), build_reflector_subagent()]
    model = ChatAnthropic(model=deps.orchestrator_model, max_tokens=4096)

    return create_deep_agent(
        tools=tools,
        instructions=instructions,
        subagents=subagents,
        model=model,
    )
