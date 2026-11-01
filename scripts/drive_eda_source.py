"""Compatibility CLI for training.data.drive_source."""
import sys
import training.data.drive_source as _module
if __name__ == "__main__" and hasattr(_module,"main"):
    _module.main()
else:
    sys.modules[__name__] = _module
