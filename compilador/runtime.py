from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ast import ArrayAccess, Assignment, Binary, Call, Dimension, For, FunctionDef, If, Literal, Node, Program, Read, Return, Unary, Variable, While, Write
from .pipeline import compile_file


class RuntimePseudocodeError(Exception):
    """Error de ejecución conservado por compatibilidad con la Fase 1."""


class ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


@dataclass
class Environment:
    inputs: list[Any]
    functions: dict[str, FunctionDef]
    parent: "Environment | None" = None
    interactive: bool = False

    def __post_init__(self) -> None:
        self.values: dict[str, Any] = {}
        self.outputs: list[str] = []

    def resolve(self, name: str) -> "Environment":
        if name in self.values:
            return self
        if self.parent is not None:
            return self.parent.resolve(name)
        raise RuntimePseudocodeError(f"variable no definida: {name}")

    def get(self, name: str) -> Any:
        return self.resolve(name).values[name]

    def set(self, name: str, value: Any) -> None:
        if name in self.values or self.parent is None:
            self.values[name] = value
            return
        try:
            self.parent.resolve(name).values[name] = value
        except RuntimePseudocodeError:
            self.values[name] = value


def display(value: Any) -> str:
    if isinstance(value, bool):
        return "Verdadero" if value else "Falso"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def require_number(value: Any, context: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RuntimePseudocodeError(f"se esperaba un número en {context}")
    return value


def eval_expr(expression: Node, env: Environment) -> Any:
    if isinstance(expression, Literal):
        return expression.value
    if isinstance(expression, Variable):
        return env.get(expression.name)
    if isinstance(expression, ArrayAccess):
        values = env.get(expression.name)
        index = require_number(eval_expr(expression.index, env), "índice de arreglo")
        if int(index) != index or index < 1 or index > len(values):
            raise RuntimePseudocodeError(f"índice fuera de rango para {expression.name}: {index}")
        return values[int(index) - 1]
    if isinstance(expression, Call):
        function = env.functions.get(expression.name)
        if function is None:
            raise RuntimePseudocodeError(f"función no definida: {expression.name}")
        if len(expression.args) != len(function.parameters):
            raise RuntimePseudocodeError(f"cantidad incorrecta de argumentos para {expression.name}")
        local = Environment([eval_expr(argument, env) for argument in expression.args], env.functions, env)
        for name, value in zip(function.parameters, local.inputs):
            local.values[name] = value
        try:
            execute_block(function.body, local)
        except ReturnSignal as signal:
            return signal.value
        if function.legacy_return_name:
            return local.get(function.legacy_return_name)
        raise RuntimePseudocodeError(f"la función {function.name} terminó sin Retornar")
    if isinstance(expression, Unary):
        value = eval_expr(expression.operand, env)
        if expression.operator in {"+", "-"}:
            number = require_number(value, "signo")
            return number if expression.operator == "+" else -number
        if expression.operator == "no":
            if not isinstance(value, bool):
                raise RuntimePseudocodeError("NO requiere un valor lógico")
            return not value
    if isinstance(expression, Binary):
        left = eval_expr(expression.left, env)
        right = eval_expr(expression.right, env)
        if expression.operator in {"y", "o"}:
            if not isinstance(left, bool) or not isinstance(right, bool):
                raise RuntimePseudocodeError(f"{expression.operator.upper()} requiere valores lógicos")
            return left and right if expression.operator == "y" else left or right
        if expression.operator in {"==", "!="}:
            return left == right if expression.operator == "==" else left != right
        if expression.operator in {">", ">=", "<", "<="}:
            try:
                return {">": left > right, ">=": left >= right, "<": left < right, "<=": left <= right}[expression.operator]
            except TypeError as exc:
                raise RuntimePseudocodeError("comparación entre tipos incompatibles") from exc
        left_number = require_number(left, "operación aritmética")
        right_number = require_number(right, "operación aritmética")
        if expression.operator == "+":
            return left_number + right_number
        if expression.operator == "-":
            return left_number - right_number
        if expression.operator == "*":
            return left_number * right_number
        if expression.operator == "/":
            if right_number == 0:
                raise RuntimePseudocodeError("división entre cero")
            return left_number / right_number
    raise RuntimePseudocodeError(f"expresión no soportada: {expression!r}")


def assign(target: Node, value: Any, env: Environment) -> None:
    if isinstance(target, Variable):
        env.set(target.name, value)
        return
    if isinstance(target, ArrayAccess):
        values = env.get(target.name)
        index = require_number(eval_expr(target.index, env), "índice de arreglo")
        if int(index) != index or index < 1 or index > len(values):
            raise RuntimePseudocodeError(f"índice fuera de rango para {target.name}: {index}")
        values[int(index) - 1] = value
        return
    raise RuntimePseudocodeError("destino de asignación inválido")


def execute_statement(statement: Node, env: Environment) -> None:
    if isinstance(statement, Write):
        line = "".join(display(eval_expr(expression, env)) for expression in statement.expressions)
        env.outputs.append(line)
        if env.interactive:
            print(line, flush=True)
    elif isinstance(statement, Read):
        for target in statement.targets:
            if env.inputs:
                value = env.inputs.pop(0)
            elif env.interactive:
                value = parse_input_value(input())
            else:
                raise RuntimePseudocodeError("faltan datos de entrada para Leer")
            assign(target, value, env)
    elif isinstance(statement, Assignment):
        assign(statement.target, eval_expr(statement.expression, env), env)
    elif isinstance(statement, If):
        condition = eval_expr(statement.condition, env)
        if not isinstance(condition, bool):
            raise RuntimePseudocodeError("la condición de Si debe ser lógica")
        execute_block(statement.then_body if condition else statement.else_body, env)
    elif isinstance(statement, While):
        guard = 0
        while eval_expr(statement.condition, env):
            execute_block(statement.body, env)
            guard += 1
            if guard > 1_000_000:
                raise RuntimePseudocodeError("Mientras excedió el límite de seguridad de iteraciones")
    elif isinstance(statement, For):
        start = require_number(eval_expr(statement.start, env), "inicio de Para")
        end = require_number(eval_expr(statement.end, env), "fin de Para")
        step = require_number(eval_expr(statement.step, env), "paso de Para") if statement.step else 1
        if int(start) != start or int(end) != end or int(step) != step or step == 0:
            raise RuntimePseudocodeError("Para requiere límites y paso enteros; el paso no puede ser cero")
        current = int(start)
        final = int(end)
        while current <= final if step > 0 else current >= final:
            env.set(statement.name, current)
            execute_block(statement.body, env)
            current += int(step)
    elif isinstance(statement, Dimension):
        size = require_number(eval_expr(statement.size, env), "tamaño de arreglo")
        if int(size) != size or size < 1:
            raise RuntimePseudocodeError("el tamaño de un arreglo debe ser un entero positivo")
        env.set(statement.name, [None] * int(size))
    elif isinstance(statement, FunctionDef):
        env.functions[statement.name] = statement
    elif isinstance(statement, Return):
        raise ReturnSignal(eval_expr(statement.expression, env))
    else:
        raise RuntimePseudocodeError(f"instrucción no soportada: {statement!r}")


def execute_block(statements: list[Node], env: Environment) -> None:
    for statement in statements:
        execute_statement(statement, env)


def parse_input_value(raw: str) -> Any:
    value = raw.strip()
    if not value:
        raise RuntimePseudocodeError("la entrada no puede estar vacía")
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def run_program(name: str | None = None, inputs: list[Any] | None = None, interactive: bool = False, source_path: str | None = None) -> list[str]:
    if source_path:
        result = compile_file(source_path)
    else:
        from pathlib import Path
        program_path = Path(__file__).resolve().parent.parent / "programas" / f"programa_{(name or '').lower()}.psc"
        result = compile_file(program_path)
    if not result.success:
        raise RuntimePseudocodeError("\n".join(error.format() for error in result.errors))
    functions: dict[str, FunctionDef] = {}
    env = Environment(list(inputs or []), functions, interactive=interactive)
    execute_block(result.ast.statements, env)
    return env.outputs
