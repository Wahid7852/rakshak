# Supports backend engine runtime behavior for syslog adapter.
def parse_syslog_line(line: str) -> dict:
    # naive placeholder parser
    parts = line.split()
    return {"raw": line, "parts": parts}
