# encoding:utf-8
"""Bounded-download guard for ``ali_api.text_to_speech_aliyun`` (probe P4).

The synthesis endpoint comes from ``config.json`` (``api_url_text_to_voice``),
so it is only as trustworthy as the deployment: an endpoint that answers with
an endless or multi-gigabyte body used to be buffered whole and written into
the managed tmp dir, and the path was handed back as a voice message.

Regression guard: an oversized body must be refused -- ``text_to_speech_aliyun``
returns ``None``, which ``AliVoice.textToVoice`` already turns into an ERROR
reply.
"""
from unittest.mock import MagicMock, patch

from common.media_download import MAX_FILE_BYTES
from voice.ali import ali_api


def test_text_to_speech_rejects_oversized_body():
    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "audio/mpeg"}
    response.content = b""  # only the pre-fix non-streaming path reads this
    response.close.return_value = None
    # Enough 64 KiB chunks to cross the cap.
    chunks = MAX_FILE_BYTES // (64 * 1024) + 10
    response.iter_content.return_value = [b"x" * (64 * 1024)] * chunks

    with patch.object(ali_api.requests, "post", return_value=response):
        written = ali_api.text_to_speech_aliyun(
            "https://example.invalid/tts", "你好", "appkey", "token"
        )

    assert written is None
