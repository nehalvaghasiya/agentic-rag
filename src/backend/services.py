"""Application-owned services and their startup factory."""

from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass

from backend.config import Settings
from backend.storage import KBStore


@dataclass(frozen=True)
class AppServices:
    """Services shared by requests within one application lifespan."""

    settings: Settings
    kb_store: KBStore


ServicesFactory = Callable[[Settings, AsyncExitStack], Awaitable[AppServices]]


async def build_services(settings: Settings, stack: AsyncExitStack) -> AppServices:
    """Construct services, registering owned resource cleanup on ``stack``.

    Register cleanup immediately after each acquisition so later startup failures
    release earlier resources. The filesystem store retains no open handles and
    needs no cleanup; persisted files belong to the user and survive shutdown.
    """
    del stack
    return AppServices(settings=settings, kb_store=KBStore(settings.data_dir))


__all__ = ["AppServices", "ServicesFactory", "build_services"]
