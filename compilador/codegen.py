from __future__ import annotations

import json
import keyword
from typing import Any

from .ast import (
    ArrayAccess,
    Assignment,
    Binary,
    Call,
    Dimension,
    For,
    FunctionDef,
    If,
    Literal,
    Node,
    Program,
    Read,
    Return,
    Unary,
    Variable,
    While,
    Write,
)


class CodeGenerationError(Exception):
    pass


class CodeGenerator:
    """Genera código ejecutable a partir del AST de la Fase 2."""

    def __init__(self, target: str) -> None:
        normalized = target.lower().strip()
        if normalized not in {"python", "javascript"}:
            raise CodeGenerationError("El lenguaje de salida debe ser Python o JavaScript")
        self.target = normalized
        self.lines: list[str] = []
        self.level = 0
        self.declared: list[set[str]] = [set()]

    def generate(self, program: Program) -> str:
        self.lines = self._header()
        self.level = 0
        self.declared = [set()]
        self.emit_statements(program.statements)
        return "\n".join(self.lines).rstrip() + "\n"

    def _header(self) -> list[str]:
        if self.target == "python":
            return [
                "# Código generado por PseudoCompiler IDE",
                "import sys",
                "",
                "# Entradas: argumentos de consola (python programa.py 10 8) o entrada estándar.",
                "_cli_inputs = iter(\" \".join(sys.argv[1:]).split())",
                "",
                "def _parse_value(raw):",
                "    value = raw.strip()",
                "    if value.lower() == 'verdadero':",
                "        return True",
                "    if value.lower() == 'falso':",
                "        return False",
                "    try:",
                "        return int(value)",
                "    except ValueError:",
                "        try:",
                "            return float(value)",
                "        except ValueError:",
                "            return value",
                "",
                "def _read():",
                "    try:",
                "        raw = next(_cli_inputs)",
                "    except StopIteration:",
                "        try:",
                "            raw = sys.stdin.readline()",
                "        except OSError:",
                "            raw = ''",
                "    if raw == '':",
                "        raise RuntimeError('Faltan datos de entrada para Leer. Use argumentos de línea de comandos o entrada estándar.')",
                "    return _parse_value(raw)",
                "",
                "def _fmt(value):",
                "    if isinstance(value, bool):",
                "        return 'Verdadero' if value else 'Falso'",
                "    if isinstance(value, float) and value.is_integer():",
                "        return str(int(value))",
                "    return str(value)",
                "",
                "def _write(*values):",
                "    print(''.join(_fmt(value) for value in values))",
                "",
                "def _inclusive_range(start, end, step=1):",
                "    if step == 0:",
                "        raise RuntimeError('El paso no puede ser cero')",
                "    return range(int(start), int(end) + (1 if step > 0 else -1), int(step))",
                "",
            ]
        return [
            "// Código generado por PseudoCompiler IDE",
            "'use strict';",
            "const fs = require('fs');",
            "// Entradas: argumentos de consola (node programa.js 10 8) o entrada estándar.",
            "const _cliInputs = process.argv.slice(2);",
            "let _cliCursor = 0;",
            "let _stdinBuffer = '';",
            "",
            "function _parseValue(raw) {",
            "  const value = raw.trim();",
            "  if (value.toLowerCase() === 'verdadero') return true;",
            "  if (value.toLowerCase() === 'falso') return false;",
            "  if (value !== '' && !Number.isNaN(Number(value))) return Number(value);",
            "  return value;",
            "}",
            "function _readStdinLine() {",
            "  const chunk = Buffer.alloc(1024);",
            "  while (true) {",
            "    const lineEnd = _stdinBuffer.indexOf('\\n');",
            "    if (lineEnd >= 0) {",
            "      const line = _stdinBuffer.slice(0, lineEnd);",
            "      _stdinBuffer = _stdinBuffer.slice(lineEnd + 1);",
            "      return line.endsWith('\\r') ? line.slice(0, -1) : line;",
            "    }",
            "    let bytesRead;",
            "    try {",
            "      bytesRead = fs.readSync(0, chunk, 0, chunk.length, null);",
            "    } catch (error) {",
            "      return null;",
            "    }",
            "    if (bytesRead === 0) {",
            "      if (_stdinBuffer.length > 0) {",
            "        const lastLine = _stdinBuffer;",
            "        _stdinBuffer = '';",
            "        return lastLine;",
            "      }",
            "      return null;",
            "    }",
            "    _stdinBuffer += chunk.toString('utf8', 0, bytesRead);",
            "  }",
            "}",
            "function _read() {",
            "  if (_cliCursor < _cliInputs.length) return _parseValue(_cliInputs[_cliCursor++]);",
            "  const raw = _readStdinLine();",
            "  if (raw === null || raw === '') throw new Error('Faltan datos de entrada para Leer. Use argumentos de línea de comandos o entrada estándar.');",
            "  return _parseValue(raw);",
            "}",
            "function _fmt(value) {",
            "  if (typeof value === 'boolean') return value ? 'Verdadero' : 'Falso';",
            "  return String(value);",
            "}",
            "function _write(...values) { console.log(values.map(_fmt).join('')); }",
            "function _inclusiveRange(start, end, step = 1) {",
            "  if (step === 0) throw new Error('El paso no puede ser cero');",
            "  const values = [];",
            "  if (step > 0) for (let value = start; value <= end; value += step) values.push(value);",
            "  else for (let value = start; value >= end; value += step) values.push(value);",
            "  return values;",
            "}",
            "",
        ]

    def emit(self, line: str = "") -> None:
        prefix = "    " * self.level if self.target == "python" else "  " * self.level
        self.lines.append(prefix + line if line else "")

    def emit_statements(self, statements: list[Node]) -> None:
        for statement in statements:
            self.emit_statement(statement)

    def emit_statement(self, statement: Node) -> None:
        if isinstance(statement, Write):
            values = ", ".join(self.expr(item) for item in statement.expressions)
            self.emit(f"_write({values})")
        elif isinstance(statement, Read):
            for target in statement.targets:
                target_text = self.target_expr(target)
                if self.target == "javascript" and isinstance(target, Variable):
                    target_text = f"{self.declare_name(target.name)} = _read()"
                else:
                    target_text = f"{target_text} = _read()"
                self.emit(target_text)
        elif isinstance(statement, Assignment):
            target_text = self.target_expr(statement.target)
            if self.target == "javascript" and isinstance(statement.target, Variable):
                target_text = f"{self.declare_name(statement.target.name)} = {self.expr(statement.expression)}"
            else:
                target_text = f"{target_text} = {self.expr(statement.expression)}"
            self.emit(target_text)
        elif isinstance(statement, If):
            keyword_if = "if" if self.target == "python" else "if"
            suffix = ":" if self.target == "python" else " {"
            self.emit(f"{keyword_if} {self.expr(statement.condition)}{suffix}")
            self.level += 1
            self.emit_statements(statement.then_body)
            if not statement.then_body:
                self.emit("pass" if self.target == "python" else "// sin instrucciones")
            self.level -= 1
            if self.target == "python":
                if statement.else_body:
                    self.emit("else:")
                    self.level += 1
                    self.emit_statements(statement.else_body)
                    self.level -= 1
            else:
                if statement.else_body:
                    self.emit("} else {")
                    self.level += 1
                    self.emit_statements(statement.else_body)
                    self.level -= 1
                self.emit("}")
        elif isinstance(statement, While):
            suffix = ":" if self.target == "python" else " {"
            self.emit(f"while {self.expr(statement.condition)}{suffix}")
            self.level += 1
            self.emit_statements(statement.body)
            if not statement.body:
                self.emit("pass" if self.target == "python" else "// sin instrucciones")
            self.level -= 1
            if self.target == "javascript":
                self.emit("}")
        elif isinstance(statement, For):
            step = self.expr(statement.step) if statement.step else "1"
            name = self.name(statement.name)
            if self.target == "python":
                self.emit(f"for {name} in _inclusive_range({self.expr(statement.start)}, {self.expr(statement.end)}, {step}):")
            else:
                self.declared[-1].add(name)
                self.emit(f"for (var {name} of _inclusiveRange({self.expr(statement.start)}, {self.expr(statement.end)}, {step})) {{")
            self.level += 1
            self.emit_statements(statement.body)
            if not statement.body:
                self.emit("pass" if self.target == "python" else "// sin instrucciones")
            self.level -= 1
            if self.target == "javascript":
                self.emit("}")
        elif isinstance(statement, Dimension):
            if self.target == "python":
                self.emit(f"{self.name(statement.name)} = [None] * (int({self.expr(statement.size)}) + 1)")
            else:
                name = self.name(statement.name)
                self.declared[-1].add(name)
                self.emit(f"var {name} = new Array(Number({self.expr(statement.size)}) + 1).fill(null);")
        elif isinstance(statement, FunctionDef):
            name = self.name(statement.name)
            params = ", ".join(self.name(param) for param in statement.parameters)
            self.emit(f"def {name}({params}):" if self.target == "python" else f"function {name}({params}) {{")
            if self.target == "javascript":
                self.declared.append({self.name(param) for param in statement.parameters})
            self.level += 1
            self.emit_statements(statement.body)
            if not statement.body:
                self.emit("pass" if self.target == "python" else "// sin instrucciones")
            self.level -= 1
            if self.target == "javascript":
                self.declared.pop()
            if self.target == "javascript":
                self.emit("}")
            self.emit()
        elif isinstance(statement, Return):
            self.emit(f"return {self.expr(statement.expression)}" + (";" if self.target == "javascript" else ""))
        else:
            raise CodeGenerationError(f"Instrucción no soportada: {type(statement).__name__}")

    def target_expr(self, node: Node) -> str:
        if isinstance(node, Variable):
            return self.name(node.name)
        if isinstance(node, ArrayAccess):
            return f"{self.name(node.name)}[{self.index_expr(node.index)}]"
        raise CodeGenerationError("Destino de asignación no soportado")

    def index_expr(self, node: Node) -> str:
        expression = self.expr(node)
        return f"int({expression})" if self.target == "python" else f"Math.trunc({expression})"

    def expr(self, node: Node) -> str:
        if isinstance(node, Literal):
            return self.literal(node.value)
        if isinstance(node, Variable):
            return self.name(node.name)
        if isinstance(node, ArrayAccess):
            return f"{self.name(node.name)}[{self.index_expr(node.index)}]"
        if isinstance(node, Call):
            return f"{self.name(node.name)}({', '.join(self.expr(arg) for arg in node.args)})"
        if isinstance(node, Unary):
            operator = {"no": "not" if self.target == "python" else "!"}.get(node.operator, node.operator)
            return f"({operator} {self.expr(node.operand)})"
        if isinstance(node, Binary):
            operator = {"y": "and" if self.target == "python" else "&&", "o": "or" if self.target == "python" else "||"}.get(node.operator, node.operator)
            return f"({self.expr(node.left)} {operator} {self.expr(node.right)})"
        raise CodeGenerationError(f"Expresión no soportada: {type(node).__name__}")

    def literal(self, value: Any) -> str:
        if isinstance(value, bool):
            if self.target == "python":
                return "True" if value else "False"
            return "true" if value else "false"
        if value is None:
            return "None" if self.target == "python" else "null"
        return json.dumps(value, ensure_ascii=False)

    def name(self, value: str) -> str:
        if self.target == "python" and keyword.iskeyword(value):
            return f"v_{value}"
        if self.target == "javascript" and value in {"class", "function", "return", "const", "let", "var", "for", "while", "if", "else", "new", "switch", "case", "default", "throw", "try", "catch"}:
            return f"v_{value}"
        return value

    def declare_name(self, value: str) -> str:
        name = self.name(value)
        if name in self.declared[-1]:
            return name
        self.declared[-1].add(name)
        return f"var {name}"


def generate_code(program: Program, target: str) -> str:
    return CodeGenerator(target).generate(program)
