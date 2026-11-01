"""Compatibility import; implementation lives in training.legacy_baseline.train_detection."""
import sys
import training.legacy_baseline.train_detection as _module
if __name__ == "__main__" and hasattr(_module,"main"):
    _module.main()
else:
    sys.modules[__name__] = _module
