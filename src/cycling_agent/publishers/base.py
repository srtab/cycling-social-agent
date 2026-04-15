"""Common publisher protocol."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol


@dataclasses.dataclass(frozen=True)
class PublishRequest:
    caption: str
    media_paths: Sequence[Path]


class Publisher(Protocol):
    """A publisher posts a draft to one platform and returns the external id."""

    def publish(self, request: PublishRequest) -> str: ...
