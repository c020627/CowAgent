# encoding:utf-8
"""Bounded-download guard for ``Vision._download_to_data_url`` (probe P4).

The image URL is model-supplied, and whatever came back was base64-encoded
whole into a single data URL: an endless or multi-gigabyte response became a
memory sink of its own (base64 costs another third on top) and then a request
the vision API answers with a payload-too-large error -- or, worse, bills.

Regression guard: a body past ``MAX_IMAGE_BYTES`` has to be refused, and a
normal image has to keep working.
"""
from unittest.mock import MagicMock, patch

import pytest

from agent.tools.vision import vision as vision_mod
from agent.tools.vision.vision import VisionAPIError
from common.media_download import MAX_IMAGE_BYTES


def _response(chunks):
    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "image/png"}
    response.content = b""  # only the pre-fix non-streaming path reads this
    response.close.return_value = None
    response.iter_content.return_value = chunks
    return response


def test_an_oversized_image_is_refused():
    # Enough 64 KiB chunks to cross the cap.
    chunks = MAX_IMAGE_BYTES // (64 * 1024) + 10
    response = _response([b"x" * (64 * 1024)] * chunks)

    with patch.object(vision_mod, "safe_get", return_value=response):
        with pytest.raises(VisionAPIError):
            vision_mod.Vision()._build_image_content("http://example.test/big.png")


def test_a_normal_image_is_still_embedded():
    """The control: the cap must not swallow the working path."""
    response = _response([b"\x89PNG\r\n\x1a\nimage"])

    with patch.object(vision_mod, "safe_get", return_value=response):
        content = vision_mod.Vision()._build_image_content("http://example.test/p.png")

    assert content["image_url"]["url"].startswith("data:image/png;base64,")
