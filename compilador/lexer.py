from __future__ import annotations

import json
from typing import Any

from .errors import ErrorCategory, ErrorCollector
from .tokens import Token


KEYWORDS = {
    "inicio", "fin", "escribir", "leer", "si", "entonces", "sino", "finsi",
    "mientras", "finmientras", "para", "hasta", "con", "paso", "hacer", "finpara",
    "dimension", "funcion", "retornar", "finfuncion", "y", "o", "no",
    "verdadero", "falso",
}

MULTI_OPERATORS = (">=", "<=", "==", "!=", "&&", "||")
SINGLE_OPERATORS = set("+-*/><=!")
DELIMITERS = set("()[],;")


class Lexer:
    """Convierte el texto fuente en tokens y conserva la ubicación exacta."""

    def __init__(self, source: str, errors: ErrorCollector | None = None) -> None:
        self.source = source
        self.errors = errors or ErrorCollector()
        self.line = 1
        self.column = 1
        self.position = 0

    def _advance(self) -> str:
        char = self.source[self.position]
        self.position += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char

    def _consume_while(self, predicate) -> str:
        start = self.position
        while self.position < len(self.source) and predicate(self.source[self.position]):
            self._advance()
        return self.source[start:self.position]

    def _error(self, message: str, line: int, column: int, lexeme: str | None = None) -> None:
        self.errors.add(ErrorCategory.LEXICAL, message, line, column, lexeme)

    def tokenize(self) -> list[Token]:
        tokens: list[Token] = []
        while self.position < len(self.source):
            char = self.source[self.position]
            if char in " \t\r":
                self._advance()
                continue
            if char == "\n":
                self._advance()
                continue
            if self.source.startswith("//", self.position) or char == "#":
                self._consume_while(lambda c: c != "\n")
                continue
            if self.source.startswith("/*", self.position):
                start_line, start_col = self.line, self.column
                self._advance(); self._advance()
                closed = False
                while self.position < len(self.source):
                    if self.source.startswith("*/", self.position):
                        self._advance(); self._advance()
                        closed = True
                        break
                    self._advance()
                if not closed:
                    self._error("comentario de bloque sin cerrar", start_line, start_col, "/*")
                continue
            if char == '"':
                tokens.append(self._string_token())
                continue
            if char.isdigit():
                tokens.append(self._number_token())
                continue
            if char.isalpha() or char == "_":
                tokens.append(self._identifier_token())
                continue
            line, col = self.line, self.column
            operator = next((op for op in MULTI_OPERATORS if self.source.startswith(op, self.position)), None)
            if operator:
                for _ in operator:
                    self._advance()
                tokens.append(Token("OPERATOR", operator, operator, line, col))
                continue
            if char in SINGLE_OPERATORS:
                self._advance()
                tokens.append(Token("OPERATOR", char, char, line, col))
                continue
            if char in DELIMITERS:
                self._advance()
                kind = "SEPARATOR" if char == ";" else "DELIMITER"
                tokens.append(Token(kind, char, char, line, col))
                continue
            self._error("carácter no válido", line, col, char)
            self._advance()
        tokens.append(Token("EOF", "", None, self.line, self.column))
        return tokens

    def _string_token(self) -> Token:
        line, col = self.line, self.column
        start = self.position
        self._advance()
        escaped = False
        closed = False
        while self.position < len(self.source):
            char = self.source[self.position]
            if char == "\n" and not escaped:
                break
            if char == '"' and not escaped:
                self._advance()
                closed = True
                break
            if char == "\\" and not escaped:
                escaped = True
            else:
                escaped = False
            self._advance()
        raw = self.source[start:self.position]
        if not closed:
            self._error("cadena sin cerrar", line, col, raw)
            return Token("STRING", raw, raw[1:], line, col)
        try:
            value: Any = json.loads(raw)
        except json.JSONDecodeError:
            self._error("secuencia de escape inválida en la cadena", line, col, raw)
            value = raw[1:-1]
        return Token("STRING", raw, value, line, col)

    def _number_token(self) -> Token:
        line, col = self.line, self.column
        raw = self._consume_while(lambda c: c.isdigit())
        if self.position < len(self.source) and self.source[self.position] == ".":
            raw += self._advance()
            if self.position >= len(self.source) or not self.source[self.position].isdigit():
                self._error("un número decimal debe tener dígitos después del punto", line, col, raw)
            else:
                raw += self._consume_while(lambda c: c.isdigit())
        value: Any = float(raw) if "." in raw else int(raw)
        return Token("NUMBER", raw, value, line, col)

    def _identifier_token(self) -> Token:
        line, col = self.line, self.column
        raw = self._consume_while(lambda c: c.isalnum() or c == "_")
        normalized = raw.casefold()
        if normalized in KEYWORDS:
            return Token("KEYWORD", raw, normalized, line, col)
        return Token("IDENTIFIER", raw, raw, line, col)
