"""Compatibility CLI for training.legacy_baseline.package_dataset."""
import sys
import training.legacy_baseline.package_dataset as _module
if __name__ == "__main__" and hasattr(_module,"main"):
    _module.main()
else:
    sys.modules[__name__] = _module
