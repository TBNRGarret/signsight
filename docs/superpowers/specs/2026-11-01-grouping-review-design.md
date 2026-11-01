# SupSign grouping review

Approved scope: task 1 of the system improvement plan, followed by the user's instruction to start. Extend the existing CPU EDA notebook for reviewing grouping before deciding whether to change the dataset. Training and changing splits are subsequent work.

## Approach

Use a read-only diagnostic replay on the prepared dataset. This works for both raw preparation and existing checked caches without modifying the preparation algorithm, recipe hashes, labels or split assignments. Adding tracing to preparation would require new cache provenance and would not explain existing caches; changing grouping immediately would pre-empt the human review.

The review reconstructs filename/capture and dHash joins in manifest order. Export only successful union edges: a bounded spanning forest, not an exhaustive similarity graph or a historical execution trace. Compare the reconstructed partition with the stored partition. Missing explicit capture metadata is reported as incomplete evidence, never inferred from filenames.

## Deliverable

- JSON summary with dataset identity, group sizes per split, concentration warnings and replay agreement.
- Complete group and edge CSVs, plus per-class box/image/group coverage across splits.
- An offline HTML report with bounded contact sheets of the largest groups and explanatory edge pairs, with source paths and labels. Escape source-controlled text; no external assets.
- Existing EDA export includes this folder. Colab prints a short summary and downloads the existing report ZIP.
- CPU only; progress while decoding cached images for dHash. No raw ZIP re-audit when a cache is available. No GPU, training or automatic relabelling.

## Constraints

All code lives in signsight/. Preserve user mobile/DESIGN.md and parent runtime data. Diagnostics write outside the dataset, verify inputs, and never mutate cache/manifests. Existing V1/V2 cache compatibility stays unchanged. Grouping heuristics do not prove trip independence or real-world driving performance.

## Acceptance

Tests demonstrate transitive merges and their reasons, namespace collisions, explicit capture metadata, no split mutation, coverage of negatives/absent classes, safe paths, escaped report text, bounded previews and notebook export in a fresh embedded runtime. Full Python regression and public-source checks pass.
