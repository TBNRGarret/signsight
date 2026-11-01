"""Compatibility import; implementation lives in training.data.audit."""
import sys
import training.data.audit as _module
if __name__ == "__main__" and hasattr(_module,"main"):
    _module.main()
else:
    sys.modules[__name__] = _module
