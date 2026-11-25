# CAR35: review labels before fine-tuning

Use [SignSight_CAR35_FineTune_Colab.ipynb](../../notebooks/SignSight_CAR35_FineTune_Colab.ipynb).
The notebook runs standalone, downloads with gdown and keeps files in `/content`.
It does not mount Drive, clone the repository, or activate weights in the application.

The initial checkpoint is the raw107 run's `best.pt` with SHA-256
`0d1f9b2feb2711189aa59b90db1d32c4f436940ab3ec98412c58ffe4289e4ea1`.
The base manifest is pinned to
`c197bb18dd27a0517ee7522803ac7f061aad7f0388abe60012c672a9378cce05`.
These identify one run, not arbitrary CAR35/V4/R3 artifacts.

## First pass: make a review pack

1. Select a CPU runtime. Leave `MODE = 'review'`.
2. Set `SOURCE_URL` to the original raw107 ZIP, or `LOCAL_SOURCE_ZIP` to an existing local copy.
3. Run the cells. Preparation filters CAR35 and recreates the fixed raw107 development split.
4. Download `car35_training_labels_to_review.zip` when prompted. The training cells do nothing in review mode.

The pack selects up to 15 train images per priority class: speed limits, pedestrian crossing,
road reserved for cars, no car U-turn and no car right turn. One image can cover multiple classes.
Selection is deterministic sampling, not a ranked active-learning algorithm. Missing annotations
and false negatives also need manual review; sampling existing labels will not find every one.

## Correct labels and add real photos

Unzip the pack. Keep `review.json` unchanged and retain this layout at the ZIP root
or inside one enclosing folder (the loader finds that folder automatically):

```text
review.json
review.csv
classes.txt
images/<image>.png
labels/<image>.txt
```

Use a YOLO detection annotation editor, preserving all 35 class IDs from `classes.txt`.
Each label line is `class_id center_x center_y width height`, normalized to the full image.
Annotate every visible CAR35 object, including small signs. A blank label is valid only after
confirming there are no selected CAR35 signs. Do not alter pixels of existing images.

`review.csv` must have these columns, in order:

```csv
image,label,split,group,reviewed
images/example.jpg,labels/example.txt,train,capture_trip_A,yes
```

Rows initially say `no`. Set `yes` only after checking the image and its annotations.
For existing images, retain the original split and group. New photos may use `train` or `val`;
assign the same physical sign/capture trip to one split and a meaningful group.
Do not move baseline validation/test images into train. Do not add test images to the pack.
The two previously failing photos are regression examples once used for development;
they are not a representative independent field test.

Zip the edited files together and upload that small ZIP to obtain `REVIEW_URL`.
Keep exactly one `review.json` and its sibling `review.csv`, with images/labels relative to that folder.
Missing metadata, multiple packs and missing CSV-referenced files give explicit errors;
the loader still checks the original ZIP hash and baseline identity, without rewriting the archive.
At least one train row must be marked reviewed=yes. Reviewed labels may remain unchanged
when already correct; the notebook allows further fine-tuning on that verified dataset.
The manifest records reviewed, unchanged, corrected and added counts separately.
Changing numeric formatting or newlines alone does not count as a label correction.
The historical R3 patch cannot be applied to this differently bound raw107 manifest.

## Second pass: fine-tune and compare

1. Select GPU runtime and set `MODE = 'train'`. Run config and install again.
2. Fill `SOURCE_URL`, `REVIEW_URL` and `CHECKPOINT_URL`. The last URL is a results ZIP containing
   `run/weights/best.pt`; a small ZIP with just that member avoids downloading every periodic checkpoint.
   Alternatively set `LOCAL_CHECKPOINT` to an existing `.pt` file.
3. Run through baseline evaluation, fine-tuning, comparison and export.

Ultralytics is pinned to `8.4.173` for both evaluations and training. Restart the runtime if an
older imported module is still resident. The controlled pilot defaults to 15 epochs, 640 px, batch 8,
explicit AdamW at 0.0003, patience 5, cosine decay, mosaic 0.1 and no horizontal/vertical flip.
`MODE='train'` is the default for an already reviewed CSV. The notebook passes these options explicitly;
do not replace the helper call with an unconfigured `YOLO.train()` call. This is a starting experiment,
not a guaranteed improvement. A new run starts from the initial checkpoint with `resume=False`.

The workflow creates a separate reviewed dataset, preserving all base images/split assignments.
Budget extra space roughly equal to the prepared dataset plus the new images; no full dataset
ZIP is created. New images are screened against other splits by byte hash and dHash distance 4.
This heuristic can reject unrelated lookalikes or miss related scenes. Resolve a collision by
reviewing/removing a new image or correcting its capture assignment; do not disable the guard
to force a better metric. Existing scene overlap in the development benchmark is not repaired.

Baseline and candidate use the same reviewed validation labels and evaluation settings.
Set optional `REGRESSION_URL` to a small shared ZIP of development/failure photos. Before export,
the notebook runs both checkpoints at confidence 0.35 and 0.05 and saves `photo_probe.json` with
classes, confidence and boxes. This is a regression probe, not independent field accuracy.
Inspect `comparison.json`, the per-class validation reports, curves and false positives.
Keep `RUN_HELDOUT_TEST=False` while selecting settings; enable it only after fixing the experiment.
Collect a separate labeled car/windshield test set for field claims. Evaluation here never
automatically replaces the serving checkpoint.

Download the result ZIP before the runtime ends. It contains weights, training settings,
baseline/candidate evaluation, the overlay hash and dataset manifest, but no dataset images.
An existing fine-tune dataset is verified and reused when its base manifest and review ZIP hash match.
You can point FINE_ROOT to that dataset in the current runtime. Changed inputs need a new FINE_ROOT.
Completed runs are not overwritten; choose another RUN_NAME for another experiment.
This notebook intentionally does not resume a partial fine-tune or adopt changed data silently.

Use [active-learning review packs](car35_active_learning.md) to select new photos for the next round.

Regenerate the notebook with `python -m training.notebooks.finetune`.

References: [Ultralytics training](https://docs.ultralytics.com/modes/train),
[annotation](https://docs.ultralytics.com/guides/data-collection-and-annotation),
[model testing](https://docs.ultralytics.com/guides/model-testing).
