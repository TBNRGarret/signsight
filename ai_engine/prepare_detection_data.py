"""Compatibility import; implementation lives in training.legacy_baseline.prepare_detection_data."""
import sys
import training.legacy_baseline.prepare_detection_data as _module
if __name__ == "__main__" and hasattr(_module,"main"):
    _module.main()
else:
    sys.modules[__name__] = _module
