# encoding:utf-8
"""Bounded-download guard for ``LinkAIVoice.textToVoice`` (probe P4).

The TTS endpoint is ``{linkai_api_base}/v1/audio/speech`` and
``linkai_api_base`` is operator config, so the endpoint that answers is only as
trustworthy as the deployment: a misconfigured or hostile one can stream an
unbounded body straight into the managed tmp dir. Regression guard: an
oversized response must be refused with an ERROR Reply instead of being
written to disk and handed back as a voice message.
"""
from unittest.mock import MagicMock, patch

import requests

from bridge.reply import ReplyType
from common.media_download import MAX_FILE_BYTES
from voice.linkai import linkai_voice
from voice.linkai.linkai_voice import LinkAIVoice


def test_text_to_voice_rejects_oversized_body():
    response = MagicMock()
    response.status_code = 200
    response.content = b""  # only the pre-fix non-streaming path reads this
    response.close.return_value = None
    # Enough 64 KiB chunks to cross the cap.
    chunks = MAX_FILE_BYTES // (64 * 1024) + 10
    response.iter_content.return_value = [b"x" * (64 * 1024)] * chunks

    with patch.object(linkai_voice, "conf", lambda: {"linkai_api_key": "k"}), \
            patch.object(linkai_voice, "apply_client_source", lambda h: h), \
            patch.object(linkai_voice, "apply_cloud_user", lambda h: h), \
            patch.object(requests, "post", return_value=response):
        reply = LinkAIVoice().textToVoice("hello")

    assert reply.type == ReplyType.ERROR
