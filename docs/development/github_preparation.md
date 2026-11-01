# Public source checks

Work directly in this canonical checkout. `python -m scripts.check_public_source` inspects tracked source paths and likely credential patterns without copying, rewriting or exporting files. CI runs the same check. It prints paths/reasons, never matching credential values. Keep datasets, weights, runtime files and academic documents in the parent workspace. The historical one-time public exporter has been retired.
