import importlib
import pkgutil
import inspect
import sys
import os

_cache = {}

def qresolve_class_by_name(class_name: str):
    """
    Dynamically resolves a class by name by scanning domain packages.

    Args:
        class_name (str): Name of the class to resolve (e.g., "Company").

    Returns:
        type: The resolved class object.

    Raises:
        ImportError: If the class cannot be found.
    """

    # Caminho base para os domínios
    base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "modules", "domain"))
    
    if base_path not in sys.path:
        sys.path.insert(0, base_path)

    for root, _, files in os.walk(base_path):
        for file in files:
            if not file.endswith(".py") or file.startswith("__"):
                continue

            rel_path = os.path.relpath(os.path.join(root, file), base_path)
            module_name = rel_path.replace("/", ".").replace("\\", ".").replace(".py", "")

            try:
                module = importlib.import_module(f"assets.modules.domain.{module_name}")
                for attr in dir(module):
                    obj = getattr(module, attr)
                    if isinstance(obj, type) and obj.__name__ == class_name:
                        return obj
            except Exception:
                continue

    raise ImportError(f"Class '{class_name}' not found in project.")

def xresolve_class_by_name(class_name: str):
    """
    Procura dinamicamente no projeto a classe com o nome fornecido.

    Exemplo:
        resolve_class_by_name("Company") => <class 'assets.modules.domain.company.Company'>

    Args:
        class_name (str): Nome simples da classe a localizar (ex: "Company").

    Returns:
        type: Referência da classe, se encontrada.

    Raises:
        ImportError: Se a classe não for encontrada.
    """
    if class_name in _cache:
        return _cache[class_name]

    base_path = os.getcwd()
    sys.path.insert(0, base_path)  # Garante que o root do projeto esteja no path

    for finder, module_name, is_pkg in pkgutil.walk_packages(path=[base_path]):
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if name == class_name:
                _cache[class_name] = obj  # Cache para performance
                return obj

    raise ImportError(f"Class '{class_name}' not found in project.")

_project_cache = {}

def kresolve_class_by_name(class_name: str):
    if class_name in _project_cache:
        return _project_cache[class_name]

    for path in sys.path:
        if not os.path.isdir(path) or "site-packages" in path:
            continue

        for finder, modname, ispkg in pkgutil.walk_packages([path]):
            if "setup" in modname:
                continue  # 🛡️ Skip setup.py

            try:
                module = importlib.import_module(modname)
                if hasattr(module, class_name):
                    cls = getattr(module, class_name)
                    _project_cache[class_name] = cls
                    return cls
            except SystemExit:
                # 🛡️ Prevent crash from setup.py or similar scripts
                continue
            except Exception:
                continue

    raise ImportError(f"Class '{class_name}' not found in project.")

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
    base_package = "assets.modules.domain"

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