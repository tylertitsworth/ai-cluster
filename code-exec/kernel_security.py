import sys
from importlib.util import find_spec

from jupyter_kernel_gateway.gateway.handlers import IPythonHandler


class KernelSecurity:
    """Security layer for controlling kernel execution environment"""

    def __init__(self):
        self.allowed_modules = {
            "numpy",
            "pandas",
            "matplotlib",
            "seaborn",
            "sklearn",
            "math",
            "statistics",
            "datetime",
        }
        self.blocked_modules = {"os", "subprocess", "sys", "socket"}

    def check_code(self, code):
        """Analyze code for potential security issues"""
        # Basic static analysis
        if any(blocked in code for blocked in ["eval", "exec", "__import__"]):
            raise SecurityError("Prohibited functions detected")

        # Check imports
        import_lines = [
            line
            for line in code.split("\n")
            if line.strip().startswith(("import ", "from "))
        ]

        for line in import_lines:
            module = line.split()[1].split(".")[0]
            if module in self.blocked_modules:
                raise SecurityError(f"Module {module} is not allowed")
            if module not in self.allowed_modules:
                if not self._is_stdlib_module(module):
                    raise SecurityError(f"Module {module} is not whitelisted")

    def _is_stdlib_module(self, module_name):
        """Check if a module is part of Python's standard library"""
        spec = find_spec(module_name)
        if spec is None:
            return False
        return "site-packages" not in str(spec.origin)


class SecurityError(Exception):
    pass
