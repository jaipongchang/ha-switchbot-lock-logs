"""Stub homeassistant (any submodule) so the package __init__ imports without a HA install."""
import importlib.abc
import sys
import types
from unittest.mock import MagicMock


class _HAShimFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "homeassistant" or fullname.startswith("homeassistant."):
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        if fullname == "switchbot" or fullname.startswith("switchbot."):
            return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
        return None

    def create_module(self, spec):
        mod = types.ModuleType(spec.name)
        mod.__path__ = []
        mod.__getattr__ = lambda attr: MagicMock()
        return mod

    def exec_module(self, module):
        pass


sys.meta_path.insert(0, _HAShimFinder())
