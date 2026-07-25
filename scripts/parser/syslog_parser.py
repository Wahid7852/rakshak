# Runs developer script support for syslog parser.
import re
from typing import Optional


class ParsedEvent:
    def __init__(self, host: Optional[str] = None, src_ip: Optional[str] = None,
                 username: Optional[str] = None, event_type: Optional[str] = None,
                 template_id: Optional[str] = None):
        self.host = host
        self.src_ip = src_ip
        self.username = username
        self.event_type = event_type
        self.template_id = template_id


# Common regexes for syslog lines (auth/sshd-like)
_HOST_RE = re.compile(r"^\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}\s+(?P<host>\S+)\s+")
_IP_RE = re.compile(r"(?P<ip>(?:\d{1,3}\.){3}\d{1,3})")
_USER_RE = re.compile(r"for(?: invalid user)?\s+(?P<user>\S+)")


def _extract_host(line: str) -> Optional[str]:
    m = _HOST_RE.match(line)
    if m:
        return m.group('host')
    return None


def parse_line(line: str) -> Optional[ParsedEvent]:
    """Parse a syslog/auth line and return a ParsedEvent or None.

    This is intentionally lightweight — it handles common sshd/auth log patterns
    like "Failed password for ... from <ip>", "Accepted password for ... from <ip>",
    and connection closed / preauth messages. It's not a full RFC parser but
    is sufficient for the project's streaming runner.
    """
    if not line or not line.strip():
        return None

    host = _extract_host(line)
    ip_m = _IP_RE.search(line)
    ip = ip_m.group('ip') if ip_m else None

    # Determine user if present
    user_m = _USER_RE.search(line)
    user = user_m.group('user') if user_m else None

    lowered = line.lower()
    # Map patterns to event types and template ids
    if 'invalid user' in lowered:
        etype = 'invalid_user'
        tid = 'invalid_user'
    elif 'failed password' in lowered or 'authentication failure' in lowered:
        etype = 'failed_password'
        tid = 'failed_password'
    elif 'accepted password' in lowered or 'accepted publickey' in lowered:
        etype = 'successful_auth'
        tid = 'successful_auth'
    elif 'preauth' in lowered or 'connection closed' in lowered:
        etype = 'preauth_close'
        tid = 'preauth_close'
    else:
        # fallback: generic syslog event, use a hashed snippet as template id
        etype = 'other'
        tid = None

    return ParsedEvent(host=host, src_ip=ip, username=user, event_type=etype, template_id=tid)
