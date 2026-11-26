from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import ErrorCategory, ErrorCollector


UNKNOWN = "Desconocido"
ERROR = "Error"
NUMBER_TYPES = {"Entero", "Real"}


@dataclass
class Symbol:
    name: str
    category: str
    type: str
    scope: str
    line: int
    column: int
    value: Any = None
    parameters: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "type": self.type,
            "scope": self.scope,
            "line": self.line,
            "column": self.column,
            "value": self.value,
            "parameters": self.parameters,
        }


@dataclass
class Scope:
    name: str
    parent: "Scope | None" = None
    symbols: dict[str, Symbol] = field(default_factory=dict)


class SymbolTable:
    def __init__(self, errors: ErrorCollector | None = None) -> None:
        self.errors = errors or ErrorCollector()
        self.global_scope = Scope("global")
        self.current = self.global_scope
        self._scopes: list[Scope] = [self.global_scope]

    def enter(self, name: str) -> Scope:
        scope = Scope(name, self.current)
        self.current = scope
        self._scopes.append(scope)
        return scope

    def exit(self) -> None:
        if self.current.parent is not None:
            self.current = self.current.parent

    def declare(
        self,
        name: str,
        category: str,
        type_: str,
        line: int,
        column: int,
        value: Any = None,
        parameters: list[str] | None = None,
    ) -> Symbol | None:
        if name in self.current.symbols:
            previous = self.current.symbols[name]
            self.errors.add(
                ErrorCategory.SEMANTIC,
                f"declaración duplicada de '{name}' en el ámbito '{self.current.name}' (declarado en línea {previous.line})",
                line,
                column,
                name,
            )
            return previous
        symbol = Symbol(name, category, type_, self.current.name, line, column, value, parameters or [])
        self.current.symbols[name] = symbol
        return symbol

    def lookup(self, name: str) -> Symbol | None:
        scope: Scope | None = self.current
        while scope is not None:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.parent
        return None

    def lookup_current(self, name: str) -> Symbol | None:
        return self.current.symbols.get(name)

    def rows(self) -> list[dict[str, Any]]:
        return [symbol.as_dict() for scope in self._scopes for symbol in scope.symbols.values()]
