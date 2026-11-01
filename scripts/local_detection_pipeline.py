"""Compatibility CLI for training.experiments.local_pipeline."""
import sys
import training.experiments.local_pipeline as _module
if __name__ == "__main__" and hasattr(_module,"main"):
    _module.main()
else:
    sys.modules[__name__] = _module
