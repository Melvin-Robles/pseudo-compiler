from __future__ import annotations

from .ast import (
    ArrayAccess, Assignment, Binary, Call, Dimension, For, FunctionDef, If, Literal,
    Node, Program, Read, Return, Unary, Variable, While, Write,
)
from .errors import ErrorCategory, ErrorCollector
from .tokens import Token


class Parser:
    """Parser descendente recursivo con recuperación básica por sentencia."""

    STATEMENT_STARTS = {"escribir", "leer", "si", "mientras", "para", "dimension", "funcion", "retornar"}

    def __init__(self, tokens: list[Token], errors: ErrorCollector | None = None) -> None:
        self.tokens = tokens
        self.errors = errors or ErrorCollector()
        self.position = 0
        self.function_depth = 0

    @property
    def current(self) -> Token:
        return self.tokens[min(self.position, len(self.tokens) - 1)]

    def advance(self) -> Token:
        token = self.current
        if self.position < len(self.tokens) - 1:
            self.position += 1
        return token

    def check_kw(self, value: str) -> bool:
        return self.current.kind == "KEYWORD" and self.current.value == value

    def match_kw(self, value: str) -> bool:
        if self.check_kw(value):
            self.advance()
            return True
        return False

    def check_op(self, value: str) -> bool:
        return self.current.kind == "OPERATOR" and self.current.lexeme == value

    def match_op(self, value: str) -> bool:
        if self.check_op(value):
            self.advance()
            return True
        return False

    def match_delimiter(self, value: str) -> bool:
        if self.current.kind in {"DELIMITER", "SEPARATOR"} and self.current.lexeme == value:
            self.advance()
            return True
        return False

    def expect_kw(self, value: str) -> Token:
        if self.match_kw(value):
            return self.tokens[self.position - 1]
        self.error(f"se esperaba la palabra reservada {value}")
        return self.current

    def expect_op(self, value: str) -> Token:
        if self.match_op(value):
            return self.tokens[self.position - 1]
        self.error(f"se esperaba el operador {value}")
        return self.current

    def expect_delimiter(self, value: str) -> Token:
        if self.match_delimiter(value):
            return self.tokens[self.position - 1]
        self.error(f"se esperaba el delimitador {value}")
        return self.current

    def expect_identifier(self) -> Token:
        if self.current.kind == "IDENTIFIER":
            return self.advance()
        self.error("se esperaba un identificador")
        return self.current

    def error(self, message: str) -> None:
        token = self.current
        self.errors.add(ErrorCategory.SYNTAX, message, token.line, token.column, token.lexeme or None)

    def parse(self) -> Program:
        start = self.current
        self.expect_kw("inicio")
        statements = self.parse_block({"fin"})
        self.expect_kw("fin")
        if self.current.kind != "EOF":
            self.error("no se permite contenido después de Fin")
        return Program(start.line, start.column, statements)

    def parse_block(self, terminators: set[str]) -> list[Node]:
        statements: list[Node] = []
        while self.current.kind != "EOF" and not (self.current.kind == "KEYWORD" and self.current.value in terminators):
            if self.match_delimiter(";"):
                continue
            before = self.position
            statements.append(self.parse_statement())
            if self.position == before:
                self.advance()
        return statements

    def parse_statement(self) -> Node:
        if self.match_kw("escribir"):
            token = self.tokens[self.position - 1]
            expressions = [self.parse_expression()]
            while self.match_delimiter(","):
                expressions.append(self.parse_expression())
            return Write(token.line, token.column, expressions)
        if self.match_kw("leer"):
            token = self.tokens[self.position - 1]
            targets = [self.parse_target()]
            while self.match_delimiter(","):
                targets.append(self.parse_target())
            return Read(token.line, token.column, targets)
        if self.match_kw("si"):
            token = self.tokens[self.position - 1]
            condition = self.parse_expression()
            self.expect_kw("entonces")
            then_body = self.parse_block({"sino", "finsi"})
            else_body: list[Node] = []
            if self.match_kw("sino"):
                else_body = self.parse_block({"finsi"})
            self.expect_kw("finsi")
            return If(token.line, token.column, condition, then_body, else_body)
        if self.match_kw("mientras"):
            token = self.tokens[self.position - 1]
            condition = self.parse_expression()
            self.expect_kw("hacer")
            body = self.parse_block({"finmientras"})
            self.expect_kw("finmientras")
            return While(token.line, token.column, condition, body)
        if self.match_kw("para"):
            token = self.tokens[self.position - 1]
            name_token = self.expect_identifier()
            self.expect_op("=")
            start = self.parse_expression()
            self.expect_kw("hasta")
            end = self.parse_expression()
            step = None
            if self.match_kw("con"):
                self.expect_kw("paso")
                step = self.parse_expression()
            self.expect_kw("hacer")
            body = self.parse_block({"finpara"})
            self.expect_kw("finpara")
            return For(token.line, token.column, str(name_token.value), start, end, step, body)
        if self.match_kw("dimension"):
            token = self.tokens[self.position - 1]
            name = self.expect_identifier()
            self.expect_delimiter("[")
            size = self.parse_expression()
            self.expect_delimiter("]")
            return Dimension(token.line, token.column, str(name.value), size)
        if self.match_kw("funcion"):
            return self.parse_function(self.tokens[self.position - 1])
        if self.match_kw("retornar"):
            token = self.tokens[self.position - 1]
            return Return(token.line, token.column, self.parse_expression())
        if self.current.kind == "IDENTIFIER":
            target = self.parse_target()
            self.expect_op("=")
            return Assignment(target.line, target.column, target, self.parse_expression())
        self.error("instrucción no reconocida")
        self.synchronize()
        return Literal(self.current.line, self.current.column, None)

    def parse_function(self, token: Token) -> FunctionDef:
        first = self.expect_identifier()
        legacy_name: str | None = None
        if self.match_op("="):
            legacy_name = str(first.value)
            name_token = self.expect_identifier()
        else:
            name_token = first
        self.expect_delimiter("(")
        parameters: list[str] = []
        if not self.match_delimiter(")"):
            parameters.append(str(self.expect_identifier().value))
            while self.match_delimiter(","):
                parameters.append(str(self.expect_identifier().value))
            self.expect_delimiter(")")
        self.function_depth += 1
        body = self.parse_block({"finfuncion"})
        self.function_depth -= 1
        self.expect_kw("finfuncion")
        return FunctionDef(token.line, token.column, str(name_token.value), parameters, body, legacy_name)

    def parse_target(self) -> Node:
        token = self.expect_identifier()
        if self.match_delimiter("["):
            index = self.parse_expression()
            self.expect_delimiter("]")
            return ArrayAccess(token.line, token.column, str(token.value), index)
        return Variable(token.line, token.column, str(token.value))

    def parse_expression(self) -> Node:
        return self.parse_or()

    def parse_or(self) -> Node:
        expression = self.parse_and()
        while self.match_kw("o") or self.match_op("||"):
            token = self.tokens[self.position - 1]
            expression = Binary(expression.line, expression.column, expression, "o", self.parse_and())
        return expression

    def parse_and(self) -> Node:
        expression = self.parse_not()
        while self.match_kw("y") or self.match_op("&&"):
            expression = Binary(expression.line, expression.column, expression, "y", self.parse_not())
        return expression

    def parse_not(self) -> Node:
        if self.match_kw("no") or self.match_op("!"):
            token = self.tokens[self.position - 1]
            return Unary(token.line, token.column, "no", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> Node:
        expression = self.parse_term()
        if self.current.kind == "OPERATOR" and self.current.lexeme in {"==", "!=", ">", ">=", "<", "<="}:
            operator = self.advance()
            expression = Binary(expression.line, expression.column, expression, operator.lexeme, self.parse_term())
        return expression

    def parse_term(self) -> Node:
        expression = self.parse_factor()
        while self.current.kind == "OPERATOR" and self.current.lexeme in {"+", "-"}:
            operator = self.advance()
            expression = Binary(expression.line, expression.column, expression, operator.lexeme, self.parse_factor())
        return expression

    def parse_factor(self) -> Node:
        expression = self.parse_unary()
        while self.current.kind == "OPERATOR" and self.current.lexeme in {"*", "/"}:
            operator = self.advance()
            expression = Binary(expression.line, expression.column, expression, operator.lexeme, self.parse_unary())
        return expression

    def parse_unary(self) -> Node:
        if self.current.kind == "OPERATOR" and self.current.lexeme in {"+", "-"}:
            token = self.advance()
            return Unary(token.line, token.column, token.lexeme, self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> Node:
        token = self.current
        if token.kind in {"NUMBER", "STRING"}:
            self.advance()
            return Literal(token.line, token.column, token.value)
        if token.kind == "KEYWORD" and token.value in {"verdadero", "falso"}:
            self.advance()
            return Literal(token.line, token.column, token.value == "verdadero")
        if token.kind == "IDENTIFIER":
            self.advance()
            if self.match_delimiter("("):
                args: list[Node] = []
                if not self.match_delimiter(")"):
                    args.append(self.parse_expression())
                    while self.match_delimiter(","):
                        args.append(self.parse_expression())
                    self.expect_delimiter(")")
                return Call(token.line, token.column, str(token.value), args)
            if self.match_delimiter("["):
                index = self.parse_expression()
                self.expect_delimiter("]")
                return ArrayAccess(token.line, token.column, str(token.value), index)
            return Variable(token.line, token.column, str(token.value))
        if self.match_delimiter("("):
            expression = self.parse_expression()
            self.expect_delimiter(")")
            return expression
        self.error("se esperaba una expresión")
        self.advance()
        return Literal(token.line, token.column, None)

    def synchronize(self) -> None:
        while self.current.kind != "EOF":
            if self.current.kind == "KEYWORD" and self.current.value in self.STATEMENT_STARTS | {"fin", "finsi", "finmientras", "finpara", "finfuncion", "sino"}:
                return
            if self.match_delimiter(";"):
                return
            self.advance()
