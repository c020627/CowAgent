"""``_restore_verbatim_query`` must patch the current turn, not the first match.

The model is shown the address-stripped query (``model_query``); the transcript
must keep what was typed (``query``). An older user message can contain
``model_query`` as a substring, so walking from the newest user message is the
only correct way to find the one that belongs to this turn.
"""

from agent.chat.service import ChatService


def test_patches_the_latest_user_message_not_an_older_substring_match():
    messages = [
        {"role": "user", "content": "say ok then do X"},
        {"role": "assistant", "content": "sure"},
        {"role": "user", "content": "ok"},
    ]
    restored = ChatService._restore_verbatim_query(messages, "ok", "@bot ok")
    # The current turn's input keeps its verbatim address.
    assert restored[-1]["content"] == "@bot ok"
    # The older message that merely contained the substring is untouched.
    assert restored[0]["content"] == "say ok then do X"


def test_no_match_leaves_messages_unchanged():
    messages = [{"role": "user", "content": "hello world"}]
    restored = ChatService._restore_verbatim_query(messages, "nomatch", "@bot nomatch")
    assert restored == messages
