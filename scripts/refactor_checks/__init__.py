"""Static refactor checks used by repository scripts.

The package is deliberately Qt-free: all checks inspect source files with AST
or plain text so CI can run them without launching the application.
"""
