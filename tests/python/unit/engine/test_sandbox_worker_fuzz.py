# Property tests: worker.py's parsers take untrusted bytes, must never crash.
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.engine.sandbox.worker import entropy, printable_strings, sniff_format


@given(st.binary(max_size=4096))
@settings(max_examples=200)
def test_entropy_never_crashes_and_is_bounded(data):
    e = entropy(data)
    assert 0.0 <= e <= 8.0  # max entropy for byte-valued data is log2(256) == 8


@given(st.binary(max_size=4096))
@settings(max_examples=200)
def test_sniff_format_never_crashes(data):
    fmt = sniff_format(data)
    assert isinstance(fmt, str)


@given(st.binary(max_size=4096), st.integers(min_value=1, max_value=32))
@settings(max_examples=200)
def test_printable_strings_never_crashes_and_respects_limit(data, min_len):
    strings = printable_strings(data, min_len=min_len, limit=16)
    assert len(strings) <= 16
    assert all(len(s) >= min_len for s in strings)
    assert all(s.isascii() and s.isprintable() for s in strings)
