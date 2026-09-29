# encoding:utf-8
"""Bounded-download guard for ``ZhipuAIVoice.textToVoice`` (probe P4).

The TTS endpoint is ``{zhipu_ai_api_base}/audio/speech`` and
``zhipu_ai_api_base`` is operator config, so the endpoint that answers is only
as trustworthy as the deployment: a misconfigured or hostile one can stream an
unbounded body straight into the managed tmp dir. Regression guard: an
oversized response must be refused with an ERROR Reply instead of being
written to disk and handed back as a voice message.
"""
from unittest.mock import MagicMock, patch

import requests

from bridge.reply import ReplyType
from voice.zhipuai import zhipuai_voice
from voice.zhipuai.zhipuai_voice import MAX_FILE_BYTES, ZhipuAIVoice


def test_text_to_voice_rejects_oversized_body():
    response = MagicMock()
    response.status_code = 200
    response.headers = {"Content-Type": "audio/wav"}
    response.content = b""  # only the pre-fix non-streaming path reads this
    response.close.return_value = None
    # Enough 64 KiB chunks to cross the cap.
    chunks = MAX_FILE_BYTES // (64 * 1024) + 10
    response.iter_content.return_value = [b"x" * (64 * 1024)] * chunks

    with patch.object(zhipuai_voice, "conf", lambda: {"zhipu_ai_api_key": "k"}), \
            patch.object(requests, "post", return_value=response):
        reply = ZhipuAIVoice().textToVoice("hello")

    assert reply.type == ReplyType.ERROR
