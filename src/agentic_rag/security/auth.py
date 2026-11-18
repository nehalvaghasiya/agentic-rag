"""JWT verification with strict audience and issuer checks; demo bypass only explicit demo mode."""

from __future__ import annotations

import jwt

from agentic_rag.models.principal import Principal


class AuthService:
    def __init__(self, secret: str | None, issuer: str, audience: str, demo: bool = False) -> None:
        self.secret = secret
        self.issuer = issuer
        self.audience = audience
        self.demo = demo
        if not demo and (not secret or len(secret) < 32):
            raise ValueError("Production requires a long JWT signing secret or OIDC configuration")

    def authenticate(self, bearer: str | None) -> Principal:
        if self.demo and not bearer:
            return Principal("demo-user", "demo-tenant", frozenset({"admin", "analyst"}))
        if not bearer or not bearer.startswith("Bearer ") or not self.secret:
            raise PermissionError("Authentication required")
        try:
            payload = jwt.decode(
                bearer[7:],
                self.secret,
                algorithms=["HS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["sub", "exp", "iat", "iss", "aud", "tenant_id"]},
            )
            roles = payload.get("roles", [])
            groups = payload.get("groups", [])
            if not isinstance(roles, list) or not isinstance(groups, list):
                raise PermissionError("Invalid identity claims")
            return Principal(
                str(payload["sub"]), str(payload["tenant_id"]), frozenset(roles), frozenset(groups)
            )
        except jwt.PyJWTError as exc:
            raise PermissionError("Invalid authentication token") from exc
