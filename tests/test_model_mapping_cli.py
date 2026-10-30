import json
import pytest

from ai_engine.catalog import SignCatalog, ModelClassMapping
from scripts.model_mapping import draft_mapping, main


def test_training_mapping_draft_is_explicitly_unreviewed_and_cannot_activate(tmp_path):
    catalog=SignCatalog()
    weights=tmp_path/'candidate.pt';weights.write_bytes(b'synthetic')
    draft=draft_mapping(['No_entry','Ambiguous_dataset_label'],catalog,weights)
    assert draft['classes'][0]=={'model_class_id':0,'model_name':'No_entry','catalog_id':None,'reviewed':False}
    assert draft['classes'][1]['catalog_id'] is None
    with pytest.raises(ValueError,match='reviewed'):ModelClassMapping(draft,catalog,weights)


def test_supsign_cli_can_draft_before_weights_arrive_and_never_overwrites_review(tmp_path):
    output=tmp_path/'mapping.json'
    assert main(['draft','--supsign-car35','--output',str(output)])==0
    document=json.loads(output.read_text(encoding='utf-8'))
    assert len(document['classes'])==35 and document['checkpoint_sha256'] is None
    assert not any(row['reviewed'] for row in document['classes'])
    with pytest.raises(FileExistsError):main(['draft','--supsign-car35','--output',str(output)])


def test_bind_rejects_unreviewed_rows_then_writes_a_valid_new_artifact(tmp_path):
    catalog=SignCatalog();weights=tmp_path/'best.pt';weights.write_bytes(b'fixture')
    draft=draft_mapping(['No_entry'],catalog)
    source=tmp_path/'draft.json';source.write_text(json.dumps(draft))
    output=tmp_path/'bound.json'
    args=['bind','--mapping',str(source),'--checkpoint',str(weights),'--output',str(output)]
    with pytest.raises(ValueError,match='reviewed'):main(args)
    assert not output.exists()
    draft['classes'][0].update(catalog_id=5,reviewed=True);source.write_text(json.dumps(draft))
    main(args)
    mapping=ModelClassMapping(json.loads(output.read_text()),catalog,weights)
    assert mapping.catalog_id(0)==5 and json.loads(source.read_text())['checkpoint_sha256'] is None
    with pytest.raises(FileExistsError):main(args)
