# Tests the read-only static analysis worker's pure functions.
from backend.engine.sandbox.worker import entropy, printable_strings, sniff_format


def test_entropy_of_all_equal_bytes_is_zero():
    assert entropy(b"\x00" * 100) == 0.0


def test_entropy_of_empty_bytes_is_zero():
    assert entropy(b"") == 0.0


def test_entropy_of_varied_bytes_is_high():
    assert entropy(bytes(range(256))) > 7.9


def test_sniff_format_detects_known_magic_bytes():
    assert sniff_format(b"MZ" + b"A" * 10) == "pe"
    assert sniff_format(b"\x7fELF" + b"A" * 10) == "elf"
    assert sniff_format(b"PK\x03\x04" + b"A" * 10) == "zip"
    assert sniff_format(b"%PDF" + b"A" * 10) == "pdf"
    assert sniff_format(b"\x89PNG" + b"A" * 10) == "png"


def test_sniff_format_unknown_for_random_bytes():
    assert sniff_format(b"not a known format") == "unknown"


def test_printable_strings_extracts_ascii_runs():
    data = b"\x00\x00hello world\x00\x00\x01\x02ab\x00\x00longenough\x00"
    strings = printable_strings(data, min_len=4)
    assert "hello world" in strings
    assert "longenough" in strings
    assert "ab" not in strings  # below the 4-char minimum


def test_printable_strings_respects_limit():
    data = b"\x00".join([f"str{i}".encode() for i in range(20)])
    strings = printable_strings(data, min_len=4, limit=5)
    assert len(strings) == 5
