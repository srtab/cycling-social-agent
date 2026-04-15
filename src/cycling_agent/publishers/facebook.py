"""Facebook Page publisher using the facebook-business SDK."""

from __future__ import annotations

import secrets
from typing import Any

import structlog

from cycling_agent.publishers.base import PublishRequest

log = structlog.get_logger(__name__)


class FacebookPublisher:
    """Posts photos with a caption to a Facebook Page.

    The ``page`` argument is a ``facebook_business.adobjects.page.Page`` instance
    (or a mock with the same surface — ``get_api()`` and ``["id"]``). We go
    through the SDK's low-level ``FacebookAdsApi.call`` because ``Page.create_photo``
    does not accept a ``files=`` kwarg for multipart upload.

    Note: ``ig_business_id`` is unused here but accepted for symmetry with how
    the Instagram publisher composes itself; allows both publishers to be built
    from the same factory.
    """

    def __init__(self, *, page: Any, ig_business_id: str | None, dry_run: bool) -> None:
        self._page = page
        self._dry_run = dry_run
        self._ig_business_id = ig_business_id  # not used for FB

    def publish(self, request: PublishRequest) -> str:
        if self._dry_run:
            fake_id = f"dry-run-fb-{secrets.token_hex(4)}"
            log.info("publisher.fb.dry_run", caption_preview=request.caption[:80], id=fake_id)
            return fake_id

        if not request.media_paths:
            raise ValueError("Facebook publisher requires at least one media file")
        media = request.media_paths[0]
        if not media.exists():
            raise FileNotFoundError(media)

        with media.open("rb") as fh:
            http_response = self._page.get_api().call(
                method="POST",
                path=(self._page["id"], "photos"),
                params={"caption": request.caption, "published": True},
                files={"source": fh},
            )
        response = http_response.json()
        post_id = str(response["id"])
        log.info("publisher.fb.published", id=post_id)
        return post_id
