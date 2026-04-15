"""Click-based CLI entrypoint.

Subcommands implemented in this task:
- init-db: create the SQLite schema.
- seed-sponsors: load sponsors.yaml into the DB.
- seed-style: load style example markdown files into the DB.

Additional subcommands (serve, reflect, dry-run helpers) land in later tasks.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import click

from cycling_agent.config import load_settings
from cycling_agent.db.engine import build_engine, build_session_factory, init_schema
from cycling_agent.db.loaders import load_sponsors, load_style_examples
from cycling_agent.db.models import Language
from cycling_agent.db.repo import Repository
from cycling_agent.logging import configure_logging, get_logger

log = get_logger(__name__)


def _build_repo() -> Repository:
    settings = load_settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings.db_path)
    init_schema(engine)
    return Repository(build_session_factory(engine))


@click.group()
def cli() -> None:
    """cycling-agent CLI."""


@cli.command("init-db")
def init_db_cmd() -> None:
    """Create the SQLite schema (no-op if already created)."""
    _build_repo()
    click.echo("schema initialised")


@cli.command("seed-sponsors")
@click.option(
    "--path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("data/sponsors.yaml"),
)
def seed_sponsors_cmd(path: Path) -> None:
    """Reload sponsors from YAML."""
    repo = _build_repo()
    load_sponsors(path, repo)
    click.echo(f"loaded {len(repo.list_sponsors())} sponsors from {path}")


@cli.command("seed-style")
@click.option("--lang", type=click.Choice(["pt", "en"]), required=True)
@click.option(
    "--path", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True
)
def seed_style_cmd(lang: str, path: Path) -> None:
    """Reload style examples from a markdown file."""
    repo = _build_repo()
    load_style_examples(path, Language(lang), repo)
    click.echo(f"loaded {len(repo.list_style_examples(Language(lang)))} examples for {lang}")


@cli.command("serve")
@click.option("--dry-run/--live", default=None, help="Override DRY_RUN env var")
def serve_cmd(dry_run: bool | None) -> None:
    """Run the agent + Telegram bot in the foreground."""
    from cycling_agent.main import serve_async

    settings = load_settings()
    if dry_run is not None:
        settings.dry_run = dry_run
    asyncio.run(serve_async(settings))


@cli.command("reflect")
def reflect_cmd() -> None:
    """Generate a style-guide diff proposal from recent approval feedback."""
    import datetime as _dt

    from langchain_anthropic import ChatAnthropic

    from cycling_agent.agent.reflect import run_reflect

    settings = load_settings()
    repo = _build_repo()
    llm = ChatAnthropic(model=settings.reflector_model, max_tokens=2048)
    out_dir = Path("data/reflect-proposals")
    path = run_reflect(repo=repo, llm=llm, output_dir=out_dir, now=_dt.datetime.now(_dt.UTC))
    click.echo(f"wrote proposal: {path}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
