"""Utilidades para cargar transformaciones SAP."""

import importlib
from typing import Callable, Optional


def load_transform(path: Optional[str], default: Callable):
    """Carga una función de transformación a partir de una ruta."""
    if not path:
        return default
    module_name, _, attr = path.partition(':') if ':' in path else path.rpartition('.')
    if not module_name or not attr:
        raise ValueError(f"Transformación SAP inválida: {path}")
    module = importlib.import_module(module_name)
    func = getattr(module, attr)
    if not callable(func):
        raise TypeError(f"Transformación SAP no callable: {path}")
    return func
