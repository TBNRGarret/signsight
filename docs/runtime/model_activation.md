# Reviewed model and catalog handoff

Updated 30 October 2026. Runtime supports checkpoint-specific output order through an explicit mapping. This does not establish that a SupSign model has been trained, that its labels match Vietnamese regulations, or that it is ready for field use.

## Identity and compatibility

- `/taxonomy` also publishes the fixed application-only correction `OTHER` (ID `1000000`, `Khác / Others`). It requires an existing detection and the usual correction reason/confirmation; accepted corrections keep the original AI result and have zero model confidence. It is not a YOLO output. Do not append it to a supplied model catalog or target it in a checkpoint mapping. The supplied catalog digest/class order remain unchanged, so reviewed model bundles do not need rebinding for this option. The application registry records this fixed identity separately from the checkpoint-bound entries.
- `model_class_id` is the index emitted by one checkpoint. `predicted_class` is the stable application catalog ID stored on detections/signs. They can differ.
- Keep catalog IDs 0–9, their codes and Vietnamese names exactly as supplied in `data/taxonomy.json`. Extend the JSON list with new, unique IDs/codes; never reorder model outputs to fit old IDs or repurpose an ID.
- Migration `0006_model_catalog` adds nullable provenance fields and a catalog registry. It does not renumber existing records. Old runs retain null provenance; their hashes cannot be reconstructed reliably after the fact.
- Startup records catalog identities and rejects removed/reassigned registered IDs or missing IDs referenced by persisted data. Extending a registered catalog is allowed. Model mappings bind the complete catalog and exact checkpoint by SHA256; regenerate/review the bound artifact when either changes.
- Every mapping row needs the exact ordered `model_name`, `catalog_id`, and `reviewed: true`. Review the dataset annotation examples and source definitions before accepting a correspondence. Ambiguous labels stay unreviewed. The tool never guesses legal sign codes.

## Prepare while training

Run from the canonical source checkout. Use new paths for your own artifacts:

```powershell
python -m scripts.model_mapping draft --supsign-car35 --output .cache/model-review/mapping-draft.json
```

The draft contains 35 ordered dataset names, null catalog targets/checkpoint hash and `reviewed: false` everywhere. Save a copy of `data/taxonomy.json` outside source as your working catalog. Append reviewed new sign identities there. Edit the draft's targets/review flags; keep its model order unchanged. Compare names against the exported training report and actual checkpoint before binding. For a different output order, use `draft --names-json` with an ordered JSON list instead.

## Bind and inspect after Colab

Keep the exported `best.pt`, validation JSON, results/config, dataset manifest, label review and test results together in a private runtime directory. Bind the edited mapping into a new file:

```powershell
python -m scripts.model_mapping bind --mapping .cache/model-review/mapping-draft.json --catalog .cache/model-review/catalog.json --checkpoint .cache/model-review/best.pt --output .cache/model-review/mapping.json
python -m scripts.model_mapping validate --mapping .cache/model-review/mapping.json --catalog .cache/model-review/catalog.json --checkpoint .cache/model-review/best.pt
python -m scripts.inspect_yolo_candidate --checkpoint .cache/model-review/best.pt --evaluation .cache/model-review/validation_report.json --catalog .cache/model-review/catalog.json --mapping .cache/model-review/mapping.json --output .cache/model-review/candidate-review.json --verify-model
```

Use the actual validation filename from the export. The inspection checks ordered checkpoint names, hashes, per-class validation coverage and configured targets. Field-test availability in a report is a supplied claim requiring evidence review. Passing file/mapping validation is not field acceptance. Do not tune against the locked test set.

For an isolated loopback timing run with the mapped candidate:

```powershell
python -m scripts.benchmark_demo --image .cache/model-review/sample.jpg --weights .cache/model-review/best.pt --catalog .cache/model-review/catalog.json --mapping .cache/model-review/mapping.json --device cpu --samples 20 --warmup 3 --output .cache/model-review/latency.json
```

This creates temporary accounts, SQLite and image storage. It preserves the personal runtime. Loopback upload/inference timings do not measure phone/LAN latency or detection quality.

## Activate on a copied runtime first

1. Stop the runtime, make a verified DB/images backup and restore it into a **new** directory following [deployment.md](deployment.md). Preserve its original configuration and weights separately.
2. Set absolute `DATABASE_URL` and `SIGNSIGHT_STORAGE_ROOT` for the restored directory. Set `SIGNSIGHT_YOLO_WEIGHTS`, `SIGNSIGHT_CATALOG_PATH` and `SIGNSIGHT_YOLO_MAPPING_PATH` to the reviewed candidate bundle.
3. Run `python -m backend.manage migrate`, then start Uvicorn. Inspect `/api/v1/ai/status`, authenticated `/api/v1/taxonomy`, old records and a new upload/detect/correction/review. Check raw model IDs, stable IDs, mapping/catalog hashes and the exact approved map record.
4. Default legacy weights still work without a mapping. An incompatible checkpoint or edited/unreviewed mapping makes detection unavailable; there is no CNN fallback or automatic publication.
5. After a catalog extension has been registered, preserve that catalog even if switching back to the legacy detector. To undo an incompatible schema/catalog change, restore the earlier backup into a new directory with its matching configuration. Do not delete extended records to make an old configuration start.

Production signing, trusted HTTPS, physical camera/GPS, real map providers and independent car-view evaluation remain separate acceptance steps. Catalogs, mappings, weights, photos, DBs and private review artifacts belong outside public Git.

## Launch a selected local runtime

`scripts/start_local.ps1 -RuntimeProfile ABSOLUTE_PROFILE_JSON` can select a copied runtime and model bundle without replacing the legacy checkpoint. The optional profile overrides these settings only:

```json
{
  "database_url": "sqlite:///ABSOLUTE_PATH_TO_COPIED_DATABASE",
  "storage_root": "ABSOLUTE_PATH_TO_COPIED_IMAGES",
  "yolo_weights": "ABSOLUTE_PATH_TO_BEST_PT",
  "catalog_path": "ABSOLUTE_PATH_TO_CATALOG_JSON",
  "yolo_mapping_path": "ABSOLUTE_PATH_TO_MAPPING_JSON",
  "yolo_device": "0",
  "yolo_confidence": 0.35
}
```

Keep this file outside public source. Paths in the profile are absolute; `database_url` uses forward slashes. Unknown keys are rejected. Without a profile the original DataRoot layout remains the default. The launcher restores process environment values when the server exits. Model readiness and catalog/mapping validity remain backend checks; supplying a profile does not bypass them.

For a phone on the same LAN, explicitly pass `-BindAddress 0.0.0.0` for that run; the source launcher default remains loopback. HTTP LAN supports testing photo selection/upload, while browser GPS needs trusted HTTPS. Manual pin confirmation remains available. Camera/GPS behavior on physical devices still requires hands-on testing.
