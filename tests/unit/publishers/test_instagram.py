"""Tests for the Instagram publisher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cycling_agent.publishers.base import PublishRequest
from cycling_agent.publishers.instagram import InstagramPublisher


def _request(tmp_path: Path) -> PublishRequest:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
    return PublishRequest(caption="Hello", media_paths=[img])


def test_publish_executes_three_step_flow(tmp_path: Path) -> None:
    fake_page = MagicMock()
    fake_page.create_photo.return_value = {
        "id": "5555",
        "images": [{"source": "https://scontent.fb.example/image.jpg"}],
    }
    fake_ig = MagicMock()
    fake_ig.create_media.return_value = {"id": "container-1"}
    fake_ig.publish_media.return_value = {"id": "ig-post-1"}

    publisher = InstagramPublisher(page=fake_page, ig=fake_ig, dry_run=False)
    post_id = publisher.publish(_request(tmp_path))
    assert post_id == "ig-post-1"

    fake_page.create_photo.assert_called_once()
    fb_kwargs = fake_page.create_photo.call_args.kwargs
    assert fb_kwargs["params"]["published"] is False

    fake_ig.create_media.assert_called_once_with(
        params={"image_url": "https://scontent.fb.example/image.jpg", "caption": "Hello"}
    )
    fake_ig.publish_media.assert_called_once_with(params={"creation_id": "container-1"})


def test_publish_dry_run_skips_api(tmp_path: Path) -> None:
    publisher = InstagramPublisher(page=MagicMock(), ig=MagicMock(), dry_run=True)
    post_id = publisher.publish(_request(tmp_path))
    assert post_id.startswith("dry-run-ig-")


def test_publish_raises_when_fb_upload_returns_no_url(tmp_path: Path) -> None:
    fake_page = MagicMock()
    fake_page.create_photo.return_value = {"id": "5555", "images": []}
    publisher = InstagramPublisher(page=fake_page, ig=MagicMock(), dry_run=False)
    with pytest.raises(RuntimeError, match="image url"):
        publisher.publish(_request(tmp_path))
