"""The two supported notebooks must build without the retired combined builder."""
import json
from pathlib import Path


def test_supported_notebooks_do_not_depend_on_combined_builder(monkeypatch):
    import scripts.generate_supsign_notebook as generator
    def retired():
        raise AssertionError('Combined notebook builder has been retired')
    monkeypatch.setattr(generator, 'build_notebook', retired, raising=False)
    for builder, name in (
        (generator.build_eda_notebook, 'SignSight_SupSign_EDA_Colab.ipynb'),
        (generator.build_train_notebook, 'SignSight_SupSign_YOLO11s_Train_Colab.ipynb'),
    ):
        notebook = builder()
        assert notebook == json.loads((Path(__file__).parents[1]/'notebooks'/name).read_text(encoding='utf-8'))


def test_embedded_notebooks_are_stable_across_filesystem_enumeration_order(monkeypatch):
    from training.notebooks import build_eda_notebook
    expected=build_eda_notebook()
    original=Path.rglob
    monkeypatch.setattr(Path,'rglob',lambda self,pattern:iter(reversed(list(original(self,pattern)))))
    assert build_eda_notebook()==expected
