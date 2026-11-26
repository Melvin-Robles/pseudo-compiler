from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    LEXICAL = "léxico"
    SYNTAX = "sintáctico"
    SEMANTIC = "semántico"


@dataclass(frozen=True)
class CompilerError:
    category: ErrorCategory
    message: str
    line: int
    column: int
    lexeme: str | None = None
    suggestion: str | None = None

    def format(self) -> str:
        location = f"Línea {self.line}, columna {self.column}"
        suffix = f" Elemento: {self.lexeme!r}." if self.lexeme else ""
        advice = f" Sugerencia: {self.suggestion}." if self.suggestion else ""
        return f"Error {self.category.value} [{location}]: {self.message}.{suffix}{advice}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "lexeme": self.lexeme,
            "suggestion": self.suggestion,
            "formatted": self.format(),
        }


class ErrorCollector:
    def __init__(self) -> None:
        self.errors: list[CompilerError] = []

    def add(
        self,
        category: ErrorCategory,
        message: str,
        line: int,
        column: int,
        lexeme: str | None = None,
        suggestion: str | None = None,
    ) -> None:
        self.errors.append(
            CompilerError(
                category,
                message,
                line,
                column,
                lexeme,
                suggestion or self._suggestion_for(category, message),
            )
        )

    @staticmethod
    def _suggestion_for(category: ErrorCategory, message: str) -> str:
        """Genera una orientación breve y accionable para la defensa."""
        lowered = message.casefold()
        if category == ErrorCategory.LEXICAL:
            if "comentario de bloque" in lowered:
                return "cierre el comentario con */"
            if "cadena" in lowered:
                return "cierre la cadena con comillas dobles y revise sus escapes"
            if "decimal" in lowered:
                return "escriba dígitos después del punto decimal"
            return "revise el carácter y use únicamente símbolos definidos por la gramática"
        if category == ErrorCategory.SYNTAX:
            if "se esperaba la palabra reservada" in lowered:
                return "agregue la palabra reservada indicada o revise el cierre del bloque"
            if "se esperaba el delimitador" in lowered:
                return "agregue el delimitador indicado y revise el agrupamiento"
            if "se esperaba el operador" in lowered:
                return "agregue el operador indicado entre los operandos"
            if "identificador" in lowered:
                return "use un nombre de variable válido"
            return "revise la instrucción actual y sincronice con el inicio o cierre del bloque"
        if "no declarado" in lowered or "no definida" in lowered:
            return "declare o asigne el identificador antes de utilizarlo"
        if "duplicada" in lowered:
            return "cambie el nombre o elimine la declaración repetida en ese ámbito"
        if "condición" in lowered or "requiere" in lowered:
            return "use una expresión del tipo esperado"
        if "asignación incompatible" in lowered or "tipos incompatibles" in lowered:
            return "asigne un valor compatible con el tipo del símbolo"
        if "arreglo" in lowered and "índice" in lowered:
            return "use un índice entero dentro del rango del arreglo"
        if "función" in lowered:
            return "verifique el nombre y la cantidad de argumentos de la función"
        return "revise la declaración, el ámbito y el tipo del elemento relacionado"

    def extend(self, errors: list[CompilerError]) -> None:
        self.errors.extend(errors)

    def by_category(self, category: ErrorCategory) -> list[CompilerError]:
        return [error for error in self.errors if error.category == category]
