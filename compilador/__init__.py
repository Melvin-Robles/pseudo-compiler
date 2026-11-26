"""Front-end del compilador de pseudocódigo del proyecto."""

from .pipeline import CompilationResult, compile_source, compile_file

__all__ = ["CompilationResult", "compile_source", "compile_file"]
