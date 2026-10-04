"""A WeChat MP callback must answer "success" even when it fails.

The platform reads the literal body "success" as "message consumed" and retries
anything else. Both Query handlers used to `return exc`, so web.py stringified
the exception into a 200 response: the user's message got no reply, the platform
retried it, and whatever the exception said went out over the wire.
"""
import unittest
from unittest.mock import patch

import web

from channel.wechatmp import active_reply, passive_reply
from channel.wechatmp.common import verify_server


class Boom(Exception):
    pass


def _body(result):
    """What web.py puts on the wire for a handler return value.

    application.py:320-330 encodes bytes as-is and str()s everything else, with
    the status left at 200.
    """
    return b"".join(
        r if isinstance(r, bytes) else str(r).encode("utf-8") for r in [result]
    )


class HandlerErrorResponseTest(unittest.TestCase):
    """Both callbacks, driven through the real handler entry point."""

    def _run(self, module, trigger):
        """Call Query.POST with `trigger` raising, and return the response body.

        The failure is injected at web.input(), the first thing both handlers
        touch, so the real except branch runs with nothing else stubbed out.
        """
        with patch.object(web, "input", side_effect=trigger), patch.object(
            web, "data", return_value=b"<xml/>"
        ), patch.object(verify_server, "__call__", return_value=None):
            body = _body(module.Query().POST())
        return body

    def _both(self, trigger):
        return self._run(active_reply, trigger), self._run(passive_reply, trigger)

    def test_a_failed_callback_answers_success_not_the_error(self):
        for name, body in zip(("active", "passive"), self._both(Boom("boom"))):
            self.assertEqual(
                body, b"success",
                f"the {name} handler answered {body!r}, so the platform sees a "
                f"failed reply and retries the message",
            )

    def test_the_error_text_does_not_reach_the_wire(self):
        # The concrete leaks: a missing setting name from the crypto guard, and
        # request material from a signature failure.
        leaks = (
            Boom("Crypto not initialized, Please set wechatmp_aes_key in config.json"),
            Boom("Invalid signature: msg_signature=abc nonce=123 timestamp=99"),
        )
        for exc in leaks:
            for name, body in zip(("active", "passive"), self._both(exc)):
                self.assertEqual(body, b"success", f"{name}: {body!r}")
                self.assertNotIn(str(exc).encode(), body)

    def test_the_failure_is_still_recorded(self):
        # Swallowing the response must not swallow the diagnosis.
        for module in (active_reply, passive_reply):
            with patch.object(module.logger, "exception") as logged:
                self._run(module, Boom("boom"))
            self.assertTrue(
                logged.called,
                f"{module.__name__} failed without logging the traceback",
            )

    def test_a_failure_before_the_reply_still_answers_success(self):
        # Not a control on the normal path -- a well-formed message would need a
        # real signature and timestamp -- but the failure this PR is about still
        # has to come out as "success" when the handler never gets as far as
        # parsing one.
        for name, body in zip(("active", "passive"), self._both(Boom("early"))):
            self.assertEqual(body, b"success", f"{name}: {body!r}")


if __name__ == "__main__":
    unittest.main()
