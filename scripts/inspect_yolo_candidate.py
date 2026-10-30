"""Inspect a training artifact; never copies weights or changes the running API."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def inspect_candidate(checkpoint, evaluation, *, runtime_names=None,
                      minimum_precision=.85, minimum_recall=.80, verify_model=False,
                      catalog=None, mapping_path=None):
    if not all(math.isfinite(v) and 0 <= v <= 1 for v in (minimum_precision, minimum_recall)):
        raise ValueError('Metric targets must be finite values in [0, 1]')
    checkpoint, evaluation = Path(checkpoint), Path(evaluation)
    with checkpoint.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    report = json.loads(evaluation.read_text(encoding='utf-8-sig'))
    from ai_engine.catalog import SignCatalog,ModelClassMapping
    catalog=catalog if catalog is not None else SignCatalog()
    mapping=None
    if mapping_path is not None:
        mapping=ModelClassMapping(json.loads(Path(mapping_path).read_text(encoding='utf-8-sig')),catalog,checkpoint)
        if runtime_names is not None and runtime_names!=mapping.names:
            raise ValueError('Explicit runtime names conflict with the reviewed mapping')
        runtime_names=mapping.names
    if runtime_names is None:
        from ai_engine.config import TAXONOMY
        runtime_names = [item['qcvn_code'] for item in TAXONOMY]
    names = report.get('names', [])
    classes = report.get('per_class', [])
    valid_names = (isinstance(names, list) and bool(names) and
                   all(isinstance(n, str) and n for n in names) and len(set(names)) == len(names))
    numeric = lambda v: type(v) in (float, int) and math.isfinite(v) and 0 <= v <= 1
    valid_classes = valid_names and len(classes) == len(names) and not report.get('classes_without_gt')
    if valid_classes:
        valid_classes = (
            all(type(row.get('class_id')) is int for row in classes) and
            {row['class_id'] for row in classes} == set(range(len(names))) and
            all(row.get('name') == names[row['class_id']] and
                all(numeric(row.get(k)) for k in ('precision','recall','map50','map50_95'))
                for row in classes))
    metrics = report.get('metrics', {})
    validation = report.get('split') == 'val' and bool(metrics) and all(numeric(v) for v in metrics.values())
    model_verified = False
    if verify_model:
        from ai_engine.detection import configure_ultralytics
        configure_ultralytics()
        from ultralytics import YOLO
        model = YOLO(str(checkpoint), task='detect')
        actual = model.names
        actual = [actual[i] for i in range(len(actual))] if isinstance(actual, dict) else list(actual)
        model_verified = model.task == 'detect' and actual == names
    checks = {
        'checkpoint_hash_matches_report': checksum == report.get('checkpoint_sha256'),
        'validation_report': validation,
        'validation_classes_complete': bool(valid_classes),
        'validation_metric_targets_met': bool(valid_classes and all(
            c['precision'] >= minimum_precision and c['recall'] >= minimum_recall for c in classes)),
        'runtime_taxonomy_matches': valid_names and names == runtime_names,
        'independent_field_test_available': report.get('independent_field_test') is True,
        'checkpoint_model_verified': model_verified,
    }
    reasons = {
        'checkpoint_hash_matches_report': 'checkpoint_hash_mismatch',
        'validation_report': 'validation_report_missing_or_invalid',
        'validation_classes_complete': 'validation_classes_missing_or_invalid',
        'validation_metric_targets_met': 'validation_metric_targets_not_met',
        'runtime_taxonomy_matches': 'runtime_taxonomy_mismatch',
        'independent_field_test_available': 'independent_field_test_missing',
        'checkpoint_model_verified': 'checkpoint_model_not_verified',
    }
    return {'checkpoint_sha256': checksum,'catalog_sha256':catalog.sha256,
            'mapping_sha256':mapping.sha256 if mapping else None, 'names': names, 'checks': checks,
            'blockers': [reasons[key] for key, passed in checks.items() if not passed],
            'targets': {'per_class_precision':minimum_precision,'per_class_recall':minimum_recall},
            'ready_for_runtime': all(checks.values()),
            'limitations': 'Report-only assessment unless --verify-model is supplied. Field-test provenance '
                           'is a supplied claim requiring evidence review. No deployment or checkpoint swap is performed.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,required=True)
    parser.add_argument('--evaluation',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--verify-model',action='store_true')
    parser.add_argument('--catalog',type=Path)
    parser.add_argument('--mapping',type=Path)
    parser.add_argument('--minimum-precision',type=float,default=.85)
    parser.add_argument('--minimum-recall',type=float,default=.80)
    args=parser.parse_args()
    from ai_engine.catalog import SignCatalog
    report=inspect_candidate(args.checkpoint,args.evaluation,verify_model=args.verify_model,
                             catalog=SignCatalog.from_file(args.catalog),mapping_path=args.mapping,
                             minimum_precision=args.minimum_precision,minimum_recall=args.minimum_recall)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print('Candidate report:',args.output)
    print('Blockers:',', '.join(report['blockers']) or 'none; review deployment acceptance evidence')


if __name__ == '__main__':
    main()
