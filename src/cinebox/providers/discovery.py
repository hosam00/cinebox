"""Auto-discovery of provider modules.

Any module inside :mod:`cinebox.providers` (other than shared/base
modules) that defines a concrete :class:`BaseProvider` subclass is picked
up and registered automatically. Contributors drop in a new file; no
registry edits required.

Ordering is deterministic: providers sort by their ``priority`` class
attribute, then by ``name``. A broken module is logged and skipped rather
than crashing the chain.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from types import ModuleType

from ..utils import Log
from .base import BaseProvider

_EXCLUDE_MODULES = frozenset({"base", "discovery", "keyword"})


def iter_provider_classes() -> list[type[BaseProvider]]:
    """Scan the providers package for concrete BaseProvider subclasses."""
    import cinebox.providers as providers_pkg

    classes: list[type[BaseProvider]] = []
    for module_info in pkgutil.iter_modules(providers_pkg.__path__):
        name = module_info.name
        if name in _EXCLUDE_MODULES or name.startswith("_"):
            continue
        classes.extend(_provider_classes_in(module_info.name))
    classes.sort(key=lambda cls: (cls.priority, cls.name))
    return classes


def _provider_classes_in(module_name: str) -> list[type[BaseProvider]]:
    module = _import_module(module_name)
    if module is None:
        return []
    found = []
    for _attr_name, obj in vars(module).items():
        if not isinstance(obj, type):
            continue
        if not issubclass(obj, BaseProvider):
            continue
        if obj is BaseProvider or inspect.isabstract(obj):
            continue
        found.append(obj)
    return found


def _import_module(name: str) -> ModuleType | None:
    try:
        return importlib.import_module(f".{name}", "cinebox.providers")
    except Exception as e:  # noqa: BLE001 - isolate broken provider modules
        Log.warn(f"Provider module {name!r} failed to import, skipping: {e}")
        return None


def build_providers() -> list[BaseProvider]:
    """Instantiate every discovered provider in priority order.

    A provider whose constructor raises is logged and skipped so the rest
    of the chain still works.
    """
    providers: list[BaseProvider] = []
    for cls in iter_provider_classes():
        try:
            providers.append(cls())
        except Exception as e:  # noqa: BLE001 - isolate bad constructors
            Log.warn(f"Provider {cls.__name__} failed to initialize, skipping: {e}")
    return providers
