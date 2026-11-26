from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import Any


@dataclass
class Node:
    line: int
    column: int


@dataclass
class Program(Node):
    statements: list[Node]


@dataclass
class Literal(Node):
    value: Any


@dataclass
class Variable(Node):
    name: str


@dataclass
class ArrayAccess(Node):
    name: str
    index: Node


@dataclass
class Call(Node):
    name: str
    args: list[Node]


@dataclass
class Unary(Node):
    operator: str
    operand: Node


@dataclass
class Binary(Node):
    left: Node
    operator: str
    right: Node


@dataclass
class Write(Node):
    expressions: list[Node]


@dataclass
class Read(Node):
    targets: list[Node]


@dataclass
class Assignment(Node):
    target: Node
    expression: Node


@dataclass
class If(Node):
    condition: Node
    then_body: list[Node]
    else_body: list[Node]


@dataclass
class While(Node):
    condition: Node
    body: list[Node]


@dataclass
class For(Node):
    name: str
    start: Node
    end: Node
    step: Node | None
    body: list[Node]


@dataclass
class Dimension(Node):
    name: str
    size: Node


@dataclass
class FunctionDef(Node):
    name: str
    parameters: list[str]
    body: list[Node]
    legacy_return_name: str | None = None


@dataclass
class Return(Node):
    expression: Node


def node_to_dict(node: Any) -> Any:
    if is_dataclass(node):
        result = {"type": type(node).__name__}
        for field in fields(node):
            result[field.name] = node_to_dict(getattr(node, field.name))
        return result
    if isinstance(node, list):
        return [node_to_dict(item) for item in node]
    return node


def tree_lines(node: Any, prefix: str = "", is_last: bool = True) -> list[str]:
    if node is None:
        return []
    if not is_dataclass(node):
        return [prefix + str(node)]
    label = type(node).__name__
    if isinstance(node, Variable):
        label += f"({node.name})"
    elif isinstance(node, Literal):
        label += f"({node.value!r})"
    elif isinstance(node, (Unary, Binary)):
        label += f"({node.operator})"
    elif isinstance(node, (FunctionDef, Dimension, For)):
        label += f"({getattr(node, 'name', '')})"
    lines = [prefix + ("+-- " if is_last else "|-- ") + label]
    children: list[Any] = []
    for field in fields(node):
        value = getattr(node, field.name)
        if field.name in {"line", "column", "name", "operator", "value", "legacy_return_name"}:
            continue
        if isinstance(value, list):
            children.extend(value)
        elif is_dataclass(value):
            children.append(value)
    for index, child in enumerate(children):
        lines.extend(tree_lines(child, prefix + ("    " if is_last else "|   "), index == len(children) - 1))
    return lines
