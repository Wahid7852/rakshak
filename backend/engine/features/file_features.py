# Extracts backend engine features for file features.
def extract_file_features(b: bytes) -> dict:
    return {
        "size": len(b),
        "entropy_approx": len(set(b[:1024]))/256.0 if b else 0.0,
    }
