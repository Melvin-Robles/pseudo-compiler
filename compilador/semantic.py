from __future__ import annotations

from .ast import (
    ArrayAccess, Assignment, Binary, Call, Dimension, For, FunctionDef, If, Literal,
    Node, Program, Read, Return, Unary, Variable, While, Write,
)
from .errors import ErrorCategory, ErrorCollector
from .symbols import ERROR, NUMBER_TYPES, UNKNOWN, Symbol, SymbolTable


def is_numeric(type_: str) -> bool:
    return type_ in NUMBER_TYPES or type_.startswith("Arreglo(") and False


def compatible(expected: str, actual: str) -> bool:
    return expected in {UNKNOWN, ERROR} or actual in {UNKNOWN, ERROR} or expected == actual or {expected, actual} == {"Entero", "Real"}


class SemanticAnalyzer:
    """Construye y valida la tabla de símbolos recorriendo el AST."""

    def __init__(self, errors: ErrorCollector | None = None) -> None:
        self.errors = errors or ErrorCollector()
        self.symbols = SymbolTable(self.errors)
        self.in_function = 0
        self.current_function: Symbol | None = None

    def analyze(self, program: Program) -> SymbolTable:
        for statement in program.statements:
            if isinstance(statement, FunctionDef):
                self._declare_function(statement)
        for statement in program.statements:
            self._statement(statement)
        return self.symbols

    def _declare_function(self, statement: FunctionDef) -> None:
        self.symbols.declare(
            statement.name,
            "función",
            UNKNOWN,
            statement.line,
            statement.column,
            parameters=statement.parameters,
        )

    def _error(self, message: str, node: Node) -> None:
        self.errors.add(ErrorCategory.SEMANTIC, message, node.line, node.column)

    def _statement(self, statement: Node) -> None:
        if isinstance(statement, Write):
            for expression in statement.expressions:
                self._expression(expression)
        elif isinstance(statement, Read):
            for target in statement.targets:
                self._read_target(target)
        elif isinstance(statement, Assignment):
            value_type = self._expression(statement.expression)
            self._assign_target(statement.target, value_type)
        elif isinstance(statement, If):
            condition_type = self._expression(statement.condition)
            if condition_type not in {"Logico", UNKNOWN, ERROR}:
                self._error("la condición de Si debe ser de tipo Logico", statement.condition)
            for child in statement.then_body:
                self._statement(child)
            for child in statement.else_body:
                self._statement(child)
        elif isinstance(statement, While):
            condition_type = self._expression(statement.condition)
            if condition_type not in {"Logico", UNKNOWN, ERROR}:
                self._error("la condición de Mientras debe ser de tipo Logico", statement.condition)
            for child in statement.body:
                self._statement(child)
        elif isinstance(statement, For):
            start_type = self._expression(statement.start)
            end_type = self._expression(statement.end)
            if start_type not in {"Entero", UNKNOWN, ERROR} or end_type not in {"Entero", UNKNOWN, ERROR}:
                self._error("los límites de Para deben ser enteros", statement)
            if statement.step is not None:
                step_type = self._expression(statement.step)
                if step_type not in {"Entero", UNKNOWN, ERROR}:
                    self._error("el paso de Para debe ser entero", statement.step)
            symbol = self.symbols.lookup_current(statement.name)
            if symbol is None:
                self.symbols.declare(statement.name, "variable de control", "Entero", statement.line, statement.column)
            elif not compatible("Entero", symbol.type):
                self._error(f"la variable de control '{statement.name}' debe ser Entero", statement)
            for child in statement.body:
                self._statement(child)
        elif isinstance(statement, Dimension):
            size_type = self._expression(statement.size)
            if size_type not in {"Entero", UNKNOWN, ERROR}:
                self._error("el tamaño de Dimension debe ser Entero", statement.size)
            existing = self.symbols.lookup_current(statement.name)
            if existing is None:
                self.symbols.declare(statement.name, "arreglo", "Arreglo(Desconocido)", statement.line, statement.column)
            elif existing.category != "arreglo":
                self._error(f"'{statement.name}' ya fue usado como {existing.category}", statement)
        elif isinstance(statement, FunctionDef):
            function = self.symbols.lookup_current(statement.name)
            previous_function = self.current_function
            self.current_function = function
            self.in_function += 1
            self.symbols.enter(f"función {statement.name}")
            for parameter in statement.parameters:
                self.symbols.declare(parameter, "parámetro", UNKNOWN, statement.line, statement.column)
            for child in statement.body:
                self._statement(child)
            self.symbols.exit()
            self.in_function -= 1
            self.current_function = previous_function
        elif isinstance(statement, Return):
            if not self.in_function:
                self._error("Retornar solo puede utilizarse dentro de una función", statement)
            return_type = self._expression(statement.expression)
            if self.current_function is not None:
                if self.current_function.type == UNKNOWN:
                    self.current_function.type = return_type
                elif not compatible(self.current_function.type, return_type):
                    self._error("los retornos de una función tienen tipos incompatibles", statement)

    def _read_target(self, target: Node) -> None:
        if isinstance(target, Variable):
            if self.symbols.lookup(target.name) is None:
                self.symbols.declare(target.name, "variable", UNKNOWN, target.line, target.column)
            return
        if isinstance(target, ArrayAccess):
            self._array_target(target)
            return
        self._error("destino inválido para Leer", target)

    def _assign_target(self, target: Node, value_type: str) -> None:
        if isinstance(target, Variable):
            symbol = self.symbols.lookup(target.name)
            if symbol is None:
                self.symbols.declare(target.name, "variable", value_type, target.line, target.column)
            elif symbol.category == "función":
                self._error(f"no se puede asignar directamente a la función '{target.name}'", target)
            elif not compatible(symbol.type, value_type):
                self._error(f"asignación incompatible: '{target.name}' es {symbol.type} y recibe {value_type}", target)
            elif symbol.type == UNKNOWN:
                symbol.type = value_type
            return
        if isinstance(target, ArrayAccess):
            array_type = self._array_target(target)
            if array_type.startswith("Arreglo("):
                element_type = array_type[8:-1]
                if not compatible(element_type, value_type):
                    self._error("el valor asignado no coincide con el tipo de los elementos del arreglo", target)
            return
        self._error("destino inválido para asignación", target)

    def _array_target(self, target: ArrayAccess) -> str:
        symbol = self.symbols.lookup(target.name)
        if symbol is None:
            self._error(f"arreglo no declarado: '{target.name}'", target)
            self._expression(target.index)
            return ERROR
        if not symbol.type.startswith("Arreglo("):
            self._error(f"'{target.name}' no es un arreglo", target)
            self._expression(target.index)
            return ERROR
        index_type = self._expression(target.index)
        if index_type not in {"Entero", UNKNOWN, ERROR}:
            self._error("el índice de un arreglo debe ser Entero", target.index)
        return symbol.type

    def _expression(self, expression: Node) -> str:
        if isinstance(expression, Literal):
            if isinstance(expression.value, bool):
                return "Logico"
            if isinstance(expression.value, int):
                return "Entero"
            if isinstance(expression.value, float):
                return "Real"
            if isinstance(expression.value, str):
                return "Cadena"
            return UNKNOWN
        if isinstance(expression, Variable):
            symbol = self.symbols.lookup(expression.name)
            if symbol is None:
                self._error(f"identificador no declarado: '{expression.name}'", expression)
                return ERROR
            return symbol.type
        if isinstance(expression, ArrayAccess):
            array_type = self._array_target(expression)
            return array_type[8:-1] if array_type.startswith("Arreglo(") else ERROR
        if isinstance(expression, Call):
            symbol = self.symbols.lookup(expression.name)
            for argument in expression.args:
                self._expression(argument)
            if symbol is None or symbol.category != "función":
                self._error(f"función no declarada: '{expression.name}'", expression)
                return ERROR
            if len(expression.args) != len(symbol.parameters):
                self._error(f"la función '{expression.name}' esperaba {len(symbol.parameters)} argumento(s) y recibió {len(expression.args)}", expression)
            return symbol.type
        if isinstance(expression, Unary):
            operand_type = self._expression(expression.operand)
            if expression.operator == "no":
                if operand_type not in {"Logico", UNKNOWN, ERROR}:
                    self._error("NO requiere un operando Logico", expression)
                return "Logico"
            if operand_type not in NUMBER_TYPES | {UNKNOWN, ERROR}:
                self._error(f"el operador {expression.operator} requiere un operando numérico", expression)
            return operand_type
        if isinstance(expression, Binary):
            left = self._expression(expression.left)
            right = self._expression(expression.right)
            if expression.operator in {"y", "o"}:
                if left not in {"Logico", UNKNOWN, ERROR} or right not in {"Logico", UNKNOWN, ERROR}:
                    self._error(f"{expression.operator.upper()} requiere operandos Logico", expression)
                return "Logico"
            if expression.operator in {"==", "!="}:
                if not compatible(left, right):
                    self._error("no se pueden comparar valores de tipos incompatibles", expression)
                return "Logico"
            if expression.operator in {">", ">=", "<", "<="}:
                if (left not in NUMBER_TYPES | {UNKNOWN, ERROR}) or (right not in NUMBER_TYPES | {UNKNOWN, ERROR}):
                    self._error("las comparaciones de orden requieren operandos numéricos", expression)
                return "Logico"
            if expression.operator in {"+", "-", "*", "/"}:
                if left not in NUMBER_TYPES | {UNKNOWN, ERROR} or right not in NUMBER_TYPES | {UNKNOWN, ERROR}:
                    self._error(f"el operador {expression.operator} requiere operandos numéricos", expression)
                if ERROR in {left, right}:
                    return ERROR
                if UNKNOWN in {left, right}:
                    return UNKNOWN
                if expression.operator == "/":
                    return "Real"
                return "Real" if "Real" in {left, right} else "Entero"
        return UNKNOWN
