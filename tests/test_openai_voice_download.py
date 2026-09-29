# encoding:utf-8
"""Bounded-download guard for ``OpenaiVoice.textToVoice`` (probe P4).

The endpoint is ``{open_ai_api_base}/audio/speech`` and ``open_ai_api_base`` is
user-configurable, so a misconfigured or hostile endpoint can stream an
unbounded body straight into the managed tmp dir. Regression guard: an
oversized response must be refused with an ERROR Reply instead of being
written to disk and handed back as a voice message.
"""
from unittest.mock import MagicMock, patch

import requests

from bridge.reply import ReplyType
from common.media_download import MAX_FILE_BYTES
from voice.openai.openai_voice import OpenaiVoice


def _conf(**values):
    """config.conf() returning the provided dict, ``None`` for missing keys."""
    cfg = MagicMock()
    cfg.get = MagicMock(side_effect=lambda key, default=None: values.get(key, default))
    return MagicMock(return_value=cfg)


def test_text_to_voice_rejects_oversized_body():
    response = MagicMock()
    response.status_code = 200
    response.content = b""  # only the pre-fix non-streaming path reads this
    response.text = ""
    response.close.return_value = None
    # Enough 64 KiB chunks to cross the cap.
    chunks = MAX_FILE_BYTES // (64 * 1024) + 10
    response.iter_content.return_value = [b"x" * (64 * 1024)] * chunks

    with patch("voice.openai.openai_voice.conf", _conf(open_ai_api_key="sk-test")), \
            patch.object(requests, "post", return_value=response):
        reply = OpenaiVoice().textToVoice("hello")

    assert reply.type == ReplyType.ERROR
