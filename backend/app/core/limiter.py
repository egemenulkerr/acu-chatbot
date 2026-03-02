from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_session_or_ip(request: Request) -> str:
    """
    Rate limiting key: X-Session-Id header varsa onu kullan, yoksa IP.
    Bu sayede aynı IP'den farklı sessionlar ayrı limitlere tabi olur
    ve proxy arkasındaki kullanıcılar birbirini etkilemez.
    """
    session_id = request.headers.get("X-Session-Id", "").strip()
    if session_id:
        return f"session:{session_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=get_session_or_ip)

# LLM fallback endpoint'leri için daha kısıtlayıcı limiter
llm_limiter = Limiter(key_func=get_session_or_ip)
