"""Tests for the Facebook publisher."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from cycling_agent.publishers.base import PublishRequest
from cycling_agent.publishers.facebook import FacebookPublisher


def _request(tmp_path: Path) -> PublishRequest:
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 50)
    return PublishRequest(
        caption="Race report\n#brandx",
        media_paths=[img],
    )


def _fake_page(page_id: str = "PAGE_ID") -> MagicMock:
    """A mock whose surface matches ``Page`` where the publisher touches it.

    The publisher calls ``page.get_api().call(...)`` and reads ``page["id"]``.
    """
    page = MagicMock()
    page.__getitem__.side_effect = lambda key: page_id if key == "id" else None
    return page


def test_publish_uploads_photo_with_caption(tmp_path: Path) -> None:
    fake_page = _fake_page()
    fake_page.get_api.return_value.call.return_value.json.return_value = {"id": "999_888"}
    publisher = FacebookPublisher(page=fake_page, ig_business_id=None, dry_run=False)
    post_id = publisher.publish(_request(tmp_path))
    assert post_id == "999_888"
    fake_page.get_api.return_value.call.assert_called_once()
    kwargs = fake_page.get_api.return_value.call.call_args.kwargs
    assert kwargs["method"] == "POST"
    assert kwargs["path"] == ("PAGE_ID", "photos")
    assert kwargs["params"]["caption"] == "Race report\n#brandx"
    assert "source" in kwargs["files"]


def test_publish_dry_run_does_not_call_api(tmp_path: Path) -> None:
    fake_page = MagicMock()
    publisher = FacebookPublisher(page=fake_page, ig_business_id=None, dry_run=True)
    post_id = publisher.publish(_request(tmp_path))
    assert post_id.startswith("dry-run-fb-")
    fake_page.get_api.assert_not_called()


def test_publish_raises_on_missing_media(tmp_path: Path) -> None:
    publisher = FacebookPublisher(page=MagicMock(), ig_business_id=None, dry_run=False)
    req = PublishRequest(caption="x", media_paths=[tmp_path / "nope.png"])
    with pytest.raises(FileNotFoundError):
        publisher.publish(req)
