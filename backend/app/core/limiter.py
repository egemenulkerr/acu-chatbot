import re

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

_SESSION_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def _get_rate_key(request: Request) -> str:
    """
    Rate limiting key: IP her zaman temel — session_id varsa ve geçerliyse
    IP:session şeklinde ek ayrım sağlar. Böylece sahte/rastgele session_id
    göndererek rate limit atlatılamaz.
    """
    ip = get_remote_address(request)
    session_id = request.headers.get("X-Session-Id", "").strip()
    if session_id and _SESSION_RE.match(session_id):
        return f"{ip}:{session_id}"
    return ip


limiter = Limiter(key_func=_get_rate_key)

llm_limiter = Limiter(key_func=_get_rate_key)
