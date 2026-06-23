"""Autoryzacja admina dla /api/admin/*. Na MVP: Bearer token z env.
W Fazie B można podmienić na login + sesję."""
import hmac

from fastapi import Header, HTTPException, status

from .config import settings


def require_admin(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ").strip()
    # hmac.compare_digest — porównanie odporne na timing.
    if not token or not hmac.compare_digest(token, settings.admin_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wymagana autoryzacja admina (Bearer token).",
        )
    return True
