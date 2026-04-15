"""Instagram Business publisher.

Implements spec §8.2 option A: upload the image to a private FB album to
obtain a CDN URL, then create an IG media container pointing at that URL,
then publish the container.
"""

from __future__ import annotations

import secrets
from typing import Any

import structlog

from cycling_agent.publishers.base import PublishRequest

log = structlog.get_logger(__name__)


class InstagramPublisher:
    """Publishes a single image + caption to Instagram Business via Graph API.

    Args:
        page: facebook_business Page object (used to upload the image privately).
        ig: facebook_business IGUser object for the linked Instagram account.
        dry_run: when True, returns a fake id and skips all API calls.
    """

    def __init__(self, *, page: Any, ig: Any, dry_run: bool) -> None:
        self._page = page
        self._ig = ig
        self._dry_run = dry_run

    def publish(self, request: PublishRequest) -> str:
        if self._dry_run:
            fake_id = f"dry-run-ig-{secrets.token_hex(4)}"
            log.info("publisher.ig.dry_run", caption_preview=request.caption[:80], id=fake_id)
            return fake_id

        if not request.media_paths:
            raise ValueError("Instagram publisher requires exactly one media file")
        media = request.media_paths[0]
        if not media.exists():
            raise FileNotFoundError(media)

        # Step 1: private upload to FB album to obtain a CDN URL. We go
        # through the SDK's low-level ``FacebookAdsApi.call`` because
        # ``Page.create_photo`` does not accept a ``files=`` kwarg for
        # multipart upload.
        with media.open("rb") as fh:
            http_response = self._page.get_api().call(
                method="POST",
                path=(self._page["id"], "photos"),
                params={"published": False, "fields": "images"},
                files={"source": fh},
            )
        fb_response = http_response.json()
        images = fb_response.get("images", [])
        if not images or "source" not in images[0]:
            raise RuntimeError("Facebook upload did not return an image url; cannot create IG container")
        image_url = images[0]["source"]
        log.info("publisher.ig.image_uploaded", url=image_url)

        # Step 2: create the IG media container
        container = self._ig.create_media(params={"image_url": image_url, "caption": request.caption})
        creation_id = container["id"]

        # Step 3: publish the container
        published = self._ig.publish_media(params={"creation_id": creation_id})
        post_id = str(published["id"])
        log.info("publisher.ig.published", id=post_id)
        return post_id
