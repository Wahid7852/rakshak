# Tests utils behavior.
import pytest

from src.utils import strip_encrypted_suffix


@pytest.mark.parametrize("inp,exp", [
    ("sample.exe.cbc.per_file.enc", "sample.exe"),
    ("virus.bin.ecb.single_key.enc", "virus.bin"),
    ("archive.tar.gz.cbc.single_key.enc", "archive.tar.gz"),
    ("nochange.txt", "nochange.txt"),
    ("weird.enc.enc", "weird"),
    ("multi.part.bin.ecb.per_file.enc", "multi.part.bin"),
    ("PAYLOAD.EXE.CBC.SINGLE_KEY.ENC", "PAYLOAD.EXE"),
    ("dual.enc.exe.ctr.per_file.enc.enc", "dual.enc.exe"),
    ("", "")
])
def test_strip_encrypted_suffix(inp, exp):
    assert strip_encrypted_suffix(inp) == exp
