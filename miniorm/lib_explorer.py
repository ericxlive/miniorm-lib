import importlib
import pkgutil
import inspect
import sys
import os

_class_cache = {}

def resolve_class_by_name(class_name: str):
    """
    Dynamically resolves a class by its name by scanning only domain modules
    inside 'assets.modules.domain'.

    Prevents circular imports, infinite loops, and accidental imports of test scripts.

    Parameters:
        class_name (str): The class name to search for.

    Returns:
        type: The resolved class.

    Raises:
        ImportError: If the class is not found in the expected domain modules.
    """
    if class_name in _class_cache:
        return _class_cache[class_name]

    # Hardcoded root package to search inside
    base_package = "app.assets.modules.domain"

    # Ensure the base package is importable
    try:
        root = importlib.import_module(base_package)
    except ImportError as e:
        raise ImportError(f"Failed to import root domain package: {base_package}") from e

    # Recursively walk through submodules of base_package
    for finder, modname, ispkg in pkgutil.walk_packages(root.__path__, prefix=base_package + "."):
        # Defensive check: ignore modules that are clearly not related (e.g., test files)
        if "test" in modname or modname.endswith(("test", "tests")):
            continue

        try:
            module = importlib.import_module(modname)
            for attr in dir(module):
                obj = getattr(module, attr)
                if isinstance(obj, type) and obj.__name__ == class_name:
                    _class_cache[class_name] = obj
                    return obj
        except Exception:
            continue

    raise ImportError(f"Class '{class_name}' not found in project.")