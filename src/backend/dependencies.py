"""Request dependencies resolved from the current application's services."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from backend.config import Settings
from backend.services import AppServices
from backend.storage import KBStore


async def get_services(request: Request) -> AppServices:
    """Return initialized services without constructing resources on demand."""
    services: AppServices | None = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="Application services are unavailable")
    return services


ServicesDep = Annotated[AppServices, Depends(get_services)]


async def get_app_settings(services: ServicesDep) -> Settings:
    """Return this application's settings snapshot."""
    return services.settings


async def get_kb_store(services: ServicesDep) -> KBStore:
    """Return this application's initialized knowledge base store."""
    return services.kb_store


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
KBStoreDep = Annotated[KBStore, Depends(get_kb_store)]

__all__ = [
    "KBStoreDep",
    "ServicesDep",
    "SettingsDep",
    "get_app_settings",
    "get_kb_store",
    "get_services",
]
