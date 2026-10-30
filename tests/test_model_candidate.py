import hashlib
import json
from scripts.inspect_yolo_candidate import inspect_candidate


def test_candidate_uses_reviewed_checkpoint_bound_mapping_without_claiming_field_acceptance(tmp_path):
    from ai_engine.catalog import SignCatalog
    from test_catalog_mapping import extended_items,mapping_data
    catalog=SignCatalog(extended_items())
    checkpoint=tmp_path/'best.pt';checkpoint.write_bytes(b'fixture')
    mapping=tmp_path/'mapping.json';mapping.write_text(json.dumps(mapping_data(catalog,checkpoint)))
    report=tmp_path/'evaluation.json'
    report.write_text(json.dumps({'names':['No_entry','Fixture_extra'],'split':'val',
        'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        'metrics':{'map50':.9},'per_class':[], 'independent_field_test':False}))
    result=inspect_candidate(checkpoint,report,catalog=catalog,mapping_path=mapping)
    assert result['checks']['runtime_taxonomy_matches'] is True
    assert result['catalog_sha256']==catalog.sha256 and len(result['mapping_sha256'])==64
    assert result['ready_for_runtime'] is False
    assert 'independent_field_test_missing' in result['blockers']


def test_candidate_metrics_cannot_make_a_35_class_model_compatible_with_legacy_runtime(tmp_path):
    checkpoint=tmp_path/'best.pt';checkpoint.write_bytes(b'fixture checkpoint')
    report=tmp_path/'evaluation_report.json'
    report.write_text(json.dumps({'names':['No_entry'], 'split':'val',
        'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        'metrics':{'metrics/mAP50(B)':.9},
        'per_class':[{'class_id':0,'name':'No_entry','precision':.95,'recall':.9,'map50':.9,'map50_95':.8}],
        'classes_without_gt':[], 'independent_field_test':False}))
    result=inspect_candidate(checkpoint,report,runtime_names=['P.102'])
    assert result['checks']['validation_metric_targets_met'] is True
    assert result['checks']['runtime_taxonomy_matches'] is False
    assert result['ready_for_runtime'] is False
    assert 'runtime_taxonomy_mismatch' in result['blockers']
    assert 'independent_field_test_missing' in result['blockers']


def test_candidate_rejects_metrics_for_different_weights_or_missing_class_ground_truth(tmp_path):
    checkpoint=tmp_path/'best.pt';checkpoint.write_bytes(b'fixture')
    report=tmp_path/'evaluation_report.json'
    report.write_text(json.dumps({'names':['A','B'],'split':'val','checkpoint_sha256':'0'*64,
        'metrics':{'metrics/mAP50(B)':.99},'per_class':[], 'classes_without_gt':['B']}))
    result=inspect_candidate(checkpoint,report,runtime_names=['A','B'])
    assert result['ready_for_runtime'] is False
    assert 'checkpoint_hash_mismatch' in result['blockers']
    assert 'validation_classes_missing_or_invalid' in result['blockers']
