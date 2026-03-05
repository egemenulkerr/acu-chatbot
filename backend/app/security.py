from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings


admin_security = HTTPBearer(auto_error=False)


def require_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(admin_security)) -> None:
    """
    Ortak admin doğrulama dependency'si.

    Authorization: Bearer <ADMIN_SECRET_TOKEN>
    """
    token = settings.admin_secret_token
    if not token:
        raise HTTPException(status_code=503, detail="Admin token yapılandırılmamış.")

    if credentials is None or credentials.credentials != token:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik admin token.")

