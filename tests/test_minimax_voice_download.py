# encoding:utf-8
"""Bounded-accumulation guard for ``MinimaxVoice.textToVoice`` (probe P4).

MiniMax streams its TTS audio as SSE frames carrying hex-encoded mp3 chunks,
and every frame was appended to a list with no ceiling: `minimax_api_base` is
operator config, so an endpoint that keeps sending frames grew the buffer
without limit, and the joined result was then written out whole.

Regression guard: a stream that carries more than `MAX_FILE_BYTES` of audio
must be refused with an ERROR Reply instead of being buffered and written.
"""
from unittest.mock import Mock, patch

from bridge.reply import ReplyType
from common.media_download import MAX_FILE_BYTES
from voice.minimax import minimax_voice
from voice.minimax.minimax_voice import MinimaxVoice

# 4 KiB of audio per frame, hex-encoded the way the API sends it.
FRAME = b'data: {"data": {"audio": "%s"}}' % (b"\x00" * (4 * 1024)).hex().encode()


def test_text_to_voice_rejects_oversized_audio_stream():
    frames = MAX_FILE_BYTES // (4 * 1024) + 10
    response = Mock(raise_for_status=lambda: None, headers={},
                    iter_lines=lambda: [FRAME] * frames)

    with patch.object(minimax_voice, "conf", lambda: {"minimax_api_key": "k"}), \
            patch.object(minimax_voice.requests, "post", return_value=response):
        reply = MinimaxVoice().textToVoice("你好")

    assert reply.type == ReplyType.ERROR
