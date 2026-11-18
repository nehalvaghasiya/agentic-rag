"""Code-level tool permission and capability enforcement."""

from agentic_rag.models.principal import Principal
from agentic_rag.models.tool import ToolSpec


class ToolPolicy:
    def authorize(self, spec: ToolSpec, principal: Principal, approved: bool = False) -> None:
        if spec.risk not in {"read", "write"}:
            raise PermissionError("Invalid tool risk")
        if spec.risk == "write" and not approved:
            raise PermissionError("Write action requires explicit approval")
        if spec.scopes and not spec.scopes.issubset(principal.roles):
            raise PermissionError("Insufficient tool permission")
