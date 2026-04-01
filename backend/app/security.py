from __future__ import annotations

import hmac
import logging
from typing import Optional
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings


logger = logging.getLogger("audit")
admin_security = HTTPBearer(auto_error=False)


def require_admin(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(admin_security),
) -> None:
    """
    Ortak admin doğrulama dependency'si.
    Başarılı ve başarısız denemeleri audit log'a yazar.
    """
    token = settings.admin_secret_token
    client_ip = request.client.host if request.client else "unknown"
    endpoint = request.url.path

    if not token:
        logger.warning("ADMIN_DENIED ip=%s path=%s reason=token_not_configured", client_ip, endpoint)
        raise HTTPException(status_code=503, detail="Admin token yapılandırılmamış.")

    if credentials is None or not hmac.compare_digest(credentials.credentials, token):
        logger.warning("ADMIN_DENIED ip=%s path=%s reason=invalid_token", client_ip, endpoint)
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik admin token.")

    logger.info("ADMIN_OK ip=%s path=%s", client_ip, endpoint)


def sanitize_url(url: str, allowed_schemes: tuple[str, ...] = ("http", "https")) -> str:
    """URL'nin güvenli bir şema kullandığını doğrula; güvensizse boş string döner."""
    try:
        parsed = urlparse(url)
        if parsed.scheme in allowed_schemes and parsed.netloc:
            return url
    except Exception:
        pass
    return ""

