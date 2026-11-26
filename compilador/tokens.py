from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Token:
    kind: str
    lexeme: str
    value: Any
    line: int
    column: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "lexeme": self.lexeme,
            "value": self.value,
            "line": self.line,
            "column": self.column,
        }
