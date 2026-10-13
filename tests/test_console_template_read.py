"""Regression tests for channel.web.core.template._read robustness.

Two real-world failure modes used to take down the whole console (HTTP 500)
because ``_read`` is on the render path for every console page:

1. A transiently-missing include fragment (e.g. mid-deploy, when files are
   being swapped) raised ``FileNotFoundError`` from ``os.path.getmtime`` before
   the on-disk cache was even consulted, so a previously-good copy could not
   save the request.
2. A fragment written in a non-UTF-8 encoding raised ``UnicodeDecodeError``
   from ``open(..., encoding='utf-8')``.

Both are now isolated: a cached copy is reused when the file cannot be stat'd,
and reads use ``errors='replace'``.
"""

from channel.web.core import template


def test_missing_include_reuses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(template, '_WEB_DIR', str(tmp_path))
    monkeypatch.setattr(template, '_cache', {})

    frag = tmp_path / 'frag.html'
    frag.write_text('hello world', encoding='utf-8')

    # First read populates the cache.
    assert template._read('frag.html') == 'hello world'

    # The file disappears (mid-deploy / transient loss). A previously-cached
    # copy must still be served instead of raising.
    frag.unlink()
    assert template._read('frag.html') == 'hello world'


def test_non_utf8_include_does_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(template, '_WEB_DIR', str(tmp_path))
    monkeypatch.setattr(template, '_cache', {})

    frag = tmp_path / 'bad.html'
    frag.write_bytes(b'\xff\xfe\x00invalid\xff')  # not valid UTF-8

    # Must return a str (with replacement chars), not raise UnicodeDecodeError.
    result = template._read('bad.html')
    assert isinstance(result, str)
