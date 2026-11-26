from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ast import Program, node_to_dict, tree_lines
from .errors import CompilerError, ErrorCategory, ErrorCollector
from .lexer import Lexer
from .parser import Parser
from .semantic import SemanticAnalyzer
from .symbols import SymbolTable
from .tokens import Token


@dataclass
class CompilationResult:
    source_name: str
    tokens: list[Token]
    ast: Program
    symbols: SymbolTable | None
    errors: list[CompilerError]

    @property
    def success(self) -> bool:
        return not self.errors

    def tokens_as_dict(self) -> list[dict[str, Any]]:
        return [token.as_dict() for token in self.tokens]

    def ast_as_dict(self) -> dict[str, Any]:
        return node_to_dict(self.ast)

    def ast_tree(self) -> str:
        return "\n".join(tree_lines(self.ast))

    def symbols_as_dict(self) -> list[dict[str, Any]]:
        return self.symbols.rows() if self.symbols else []

    def errors_as_dict(self) -> list[dict[str, Any]]:
        return [error.as_dict() for error in self.errors]

    def report(self) -> dict[str, Any]:
        return {
            "source": self.source_name,
            "success": self.success,
            "tokens": self.tokens_as_dict(),
            "ast": self.ast_as_dict(),
            "symbols": self.symbols_as_dict(),
            "errors": self.errors_as_dict(),
        }


def compile_source(source: str, source_name: str = "<memoria>") -> CompilationResult:
    errors = ErrorCollector()
    tokens = Lexer(source, errors).tokenize()
    ast = Parser(tokens, errors).parse()
    symbols = None
    if not errors.by_category(ErrorCategory.LEXICAL) and not errors.by_category(ErrorCategory.SYNTAX):
        symbols = SemanticAnalyzer(errors).analyze(ast)
    return CompilationResult(source_name, tokens, ast, symbols, errors.errors)


def compile_file(path: str | Path) -> CompilationResult:
    source_path = Path(path).expanduser().resolve()
    source = source_path.read_text(encoding="utf-8")
    return compile_source(source, str(source_path))
