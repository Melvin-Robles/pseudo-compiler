from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from compilador.codegen import generate_code  # noqa: E402
from compilador.pipeline import compile_file, compile_source  # noqa: E402


ERROR_CASES = {
    "LEXICO": {
        "label": "Error léxico",
        "description": "Símbolo inválido",
        "filename": "caso_error_lexico.psc",
    },
    "SINTACTICO": {
        "label": "Error sintáctico",
        "description": "Cierre incorrecto",
        "filename": "caso_error_sintactico.psc",
    },
    "SEMANTICO": {
        "label": "Error semántico",
        "description": "Tipos y declaraciones",
        "filename": "caso_error_semantico.psc",
    },
}


TEST_CASES = {
    "A": [
        ([4, 2, 3], ["El resultado es: 16"]),
        ([10, 5, 2], ["El resultado es: 28"]),
        ([6, 3, 4], ["El resultado es: 34"]),
    ],
    "B": [
        ([8, 80], ["Aprobado"]),
        ([7, 60], ["Reprobado por asistencia"]),
        ([4, 90], ["Reprobado por nota"]),
    ],
    "C": [
        ([4], ["El factorial es: 24", "La suma es: 20"]),
        ([5], ["El factorial es: 120", "La suma es: 30"]),
        ([1], ["El factorial es: 1", "La suma es: 2"]),
    ],
    "D": [
        ([3, 4, 9, 2], ["El promedio es: 5", "El número mayor es: 9"]),
        ([4, 10, 20, 5, 15], ["El promedio es: 12.5", "El número mayor es: 20"]),
        ([5, 1, 1, 1, 1, 1], ["El promedio es: 1", "El número mayor es: 1"]),
    ],
    "E": [
        ([5, 4], ["El área es: 20", "Clasificación: Pequeña"]),
        ([10, 8], ["El área es: 80", "Clasificación: Grande"]),
        ([6, 9], ["El área es: 54", "Clasificación: Grande"]),
    ],
}


def json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def source_for_program(program: str) -> str:
    path = ROOT / "programas" / f"programa_{program.lower()}.psc"
    return path.read_text(encoding="utf-8")


def source_for_error(case: str) -> str:
    path = ROOT / "programas" / "errores" / ERROR_CASES[case]["filename"]
    return path.read_text(encoding="utf-8")


def compile_payload(source: str, source_name: str, target: str) -> dict:
    result = compile_source(source, source_name)
    payload = result.report()
    payload.update(
        {
            "target": target,
            "generated_code": generate_code(result.ast, target) if result.success else "",
            "ast_tree": result.ast_tree(),
            "stats": {
                "tokens": len(result.tokens),
                "symbols": len(result.symbols_as_dict()),
                "errors": len(result.errors),
            },
        }
    )
    return payload


def run_generated(code: str, target: str, inputs: list[object]) -> tuple[bool, str, str]:
    suffix = ".py" if target == "python" else ".js"
    executable = sys.executable if target == "python" else shutil.which("node")
    if not executable:
        return False, "", "Node.js no está instalado en este equipo."
    with tempfile.TemporaryDirectory(prefix="pseudocompiler-") as temp_dir:
        path = Path(temp_dir) / f"salida{suffix}"
        path.write_text(code, encoding="utf-8")
        command = [executable, str(path)]
        stdin = "\n".join(str(item) for item in inputs)
        if inputs:
            stdin += "\n"
        environment = os.environ.copy()
        if target == "python":
            environment["PYTHONIOENCODING"] = "utf-8"
        try:
            completed = subprocess.run(
                command,
                input=stdin,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=6,
                cwd=ROOT,
            )
        except subprocess.TimeoutExpired:
            return False, "", "El programa superó el límite de 6 segundos."
        output = (completed.stdout or "").strip()
        error = (completed.stderr or "").strip()
        return completed.returncode == 0, output, error


def run_test_suite(target: str) -> dict:
    rows: list[dict] = []
    for program, cases in TEST_CASES.items():
        compilation = compile_payload(source_for_program(program), f"programa_{program.lower()}.psc", target)
        for index, (inputs, expected) in enumerate(cases, start=1):
            if compilation["success"]:
                ok_process, output, error = run_generated(compilation["generated_code"], target, inputs)
                actual_lines = output.splitlines()
                passed = ok_process and all(expected_line in actual_lines for expected_line in expected)
                detail = "Salida coincide con el caso esperado" if passed else (error or "La salida no coincide")
            else:
                passed = False
                actual_lines = []
                detail = "El programa no compila"
            rows.append(
                {
                    "program": program,
                    "case": index,
                    "inputs": inputs,
                    "expected": expected,
                    "actual": actual_lines,
                    "passed": passed,
                    "detail": detail,
                }
            )
    passed_count = sum(row["passed"] for row in rows)
    return {"target": target, "total": len(rows), "passed": passed_count, "failed": len(rows) - passed_count, "cases": rows}


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/programs":
            json_response(
                self,
                {
                    "programs": {key: source_for_program(key) for key in TEST_CASES},
                    "error_cases": {
                        key: {**metadata, "source": source_for_error(key)}
                        for key, metadata in ERROR_CASES.items()
                    },
                },
            )
            return
        if path == "/api/health":
            json_response(self, {"ok": True, "app": "PseudoCompiler IDE"})
            return
        self.serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path not in {"/api/compile", "/api/test-suite", "/api/run"}:
            json_response(self, {"error": "Ruta no encontrada"}, HTTPStatus.NOT_FOUND)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(size).decode("utf-8"))
            target = str(data.get("target", "python")).lower()
            if target not in {"python", "javascript"}:
                raise ValueError("Lenguaje no soportado")
            if path == "/api/test-suite":
                json_response(self, run_test_suite(target))
                return
            if path == "/api/run":
                code = str(data.get("code", ""))
                input_text = str(data.get("input_text", ""))
                inputs = input_text.splitlines()
                ok_process, output, error = run_generated(code, target, inputs)
                json_response(
                    self,
                    {
                        "success": ok_process,
                        "output": output,
                        "error": error,
                        "target": target,
                    },
                )
                return
            source = str(data.get("source", ""))
            json_response(self, compile_payload(source, str(data.get("source_name", "editor.psc")), target))
        except (ValueError, json.JSONDecodeError) as exc:
            json_response(self, {"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except Exception as exc:  # Mantiene el diagnóstico visible en la UI.
            json_response(self, {"error": f"Error interno: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def serve_static(self, path: str) -> None:
        relative = "index.html" if path in {"", "/"} else path.lstrip("/")
        candidate = (ROOT / "static" / relative).resolve()
        static_root = (ROOT / "static").resolve()
        if static_root not in candidate.parents and candidate != static_root:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = "text/html; charset=utf-8" if candidate.suffix == ".html" else "text/css; charset=utf-8" if candidate.suffix == ".css" else "application/javascript; charset=utf-8"
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Servidor local de PseudoCompiler IDE")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), AppHandler)
    browser_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    browser_url = f"http://{browser_host}:{args.port}"
    print(f"PseudoCompiler IDE disponible en {browser_url}")
    try:
        webbrowser.open_new_tab(browser_url)
    except webbrowser.Error:
        print("No se pudo abrir el navegador automáticamente. Usa la URL mostrada arriba.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
