"""Duplicate/no-progress trajectory control."""


class LoopGuard:
    def __init__(self) -> None:
        self.seen: set[tuple[str, str]] = set()

    def detect(self, name: str, arguments: dict[str, object]) -> bool:
        key = (name, repr(sorted(arguments.items())))
        if key in self.seen:
            return True
        self.seen.add(key)
        return False
