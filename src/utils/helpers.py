# Provides RAKSHAK support for helpers.
"""
Helper utilities for filename mapping and common operations.
"""

import re
from pathlib import Path
from typing import Union

_SUFFIX_RE = re.compile(r'(?:\.(?:ecb|cbc|ctr)(?:\.[^.]*)*)(?:\.enc)*$', flags=re.IGNORECASE)

def strip_encrypted_suffix(fname: Union[str, Path]) -> str:
    """
    Remove encryption-mode suffixes and trailing .enc tokens from a filename.

    Args:
        fname: Filename or path to process

    Returns:
        Filename with encryption-related suffixes removed

    Examples:
        sample.exe.cbc.per_file.enc -> sample.exe
        virus.bin.ecb.single_key.enc -> virus.bin
        archive.tar.gz.cbc.single_key.enc -> archive.tar.gz
    """
    if not fname:
        return str(fname)
    
    fname = str(fname)
    
    # First remove repeated .enc (e.g., .enc.enc)
    while fname.lower().endswith('.enc'):
        fname = fname[:-4]
    
    # Remove mode suffix patterns like .cbc.<anything> or .ecb.<anything> etc.
    new = re.sub(_SUFFIX_RE, '', fname)
    return new

def get_project_root() -> Path:
    """Get the absolute path to the project root directory."""
    return Path(__file__).parent.parent.parent

def ensure_dir(path: Union[str, Path]) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path to ensure exists
        
    Returns:
        Path object pointing to the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path