"""Authentication and user access.

The default is developer-friendly anonymous access using X-User-ID. Set API_KEY
and ALLOW_ANONYMOUS=false in production-like deployments.
"""
from __future__ import annotations

import hmac
import re

from fastapi import HTTPException, Request, status
from pydantic import BaseModel

from config import settings


class AuthContext(BaseModel):
    user_id: str
    authenticated: bool = False


class AuthService:
    def __init__(self, api_key: str | None = None, allow_anonymous: bool = True):
        self.api_key = api_key
        self.allow_anonymous = allow_anonymous

    def authenticate(self, request: Request) -> AuthContext:
        header_key = request.headers.get("x-api-key")
        user_id = request.headers.get("x-user-id") or request.query_params.get("user_id") or "guest"
        user_id = self._safe_user_id(user_id)

        if self.api_key:
            if not header_key or not hmac.compare_digest(header_key, self.api_key):
                if not self.allow_anonymous:
                    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
                return AuthContext(user_id=user_id, authenticated=False)
            return AuthContext(user_id=user_id, authenticated=True)

        if not self.allow_anonymous and user_id == "guest":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        return AuthContext(user_id=user_id, authenticated=user_id != "guest")

    def _safe_user_id(self, value: str) -> str:
        value = re.sub(r"[^a-zA-Z0-9_.@-]", "_", value.strip())[:80]
        return value or "guest"


auth_service = AuthService(settings.api_key, settings.allow_anonymous)


async def get_auth_context(request: Request) -> AuthContext:
    return auth_service.authenticate(request)
