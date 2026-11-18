"""The two supported notebooks must build without the retired combined builder."""
import json
from pathlib import Path


def test_legacy_notebooks_remain_reproducible_without_combined_builder(monkeypatch):
    import scripts.generate_supsign_notebook as generator
    def retired():
        raise AssertionError('Combined notebook builder has been retired')
    monkeypatch.setattr(generator, 'build_notebook', retired, raising=False)
    for builder, name in (
        (generator.build_eda_notebook, 'SignSight_SupSign_EDA_Colab.ipynb'),
        (generator.build_train_notebook, 'SignSight_SupSign_YOLO11s_Train_Colab.ipynb'),
    ):
        notebook = builder()
        assert notebook == json.loads((Path(__file__).parents[1]/'notebooks/legacy'/name).read_text(encoding='utf-8'))


def test_embedded_notebooks_are_stable_across_filesystem_enumeration_order(monkeypatch):
    from training.notebooks import build_eda_notebook
    expected=build_eda_notebook()
    original=Path.rglob
    monkeypatch.setattr(Path,'rglob',lambda self,pattern:iter(reversed(list(original(self,pattern)))))
    assert build_eda_notebook()==expected


def test_legacy_notebooks_exclude_unrelated_future_training_modules(monkeypatch):
    from training.notebooks import builder
    expected = builder.build_eda_notebook()
    unrelated = builder.ROOT/'training/data/unrelated_new_pipeline.py'
    original = Path.rglob
    def with_unrelated(path, pattern):
        return iter([*original(path, pattern), unrelated])
    monkeypatch.setattr(Path, 'rglob', with_unrelated)
    # An unrelated module must neither be read nor change the embedded artifact.
    assert builder.build_eda_notebook() == expected


def test_rerunning_pipeline_replaces_previously_imported_renderer(tmp_path, monkeypatch):
    """Uploading new notebook code must replace old Python module objects too."""
    import ast
    import sys
    from training.notebooks import build_eda_notebook
    from test_supsign_training import clear_embedded_modules
    from test_grouping_review import prepared_review_fixture

    fixture = tmp_path/'fixture'; fixture.mkdir()
    root, _ = prepared_review_fixture(fixture)
    code = next(''.join(c['source']) for c in build_eda_notebook()['cells'] if c['id'] == 'pipeline')
    tree = ast.parse(code)
    assignment = next(n for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'TRAINING_FILES' for t in n.targets))
    files = ast.literal_eval(assignment.value)

    # Real previous renderer behavior: renders tables/contact sheets without the
    # later global dHash section. This is executed/imported as a Python module,
    # not a mock in sys.modules.
    old = ast.parse(files['training/data/grouping_render.py'])
    class BeforeGlobalDhash(ast.NodeTransformer):
        def visit_Assign(self, node):
            if (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == '_dhash_review'):
                return ast.Assign(targets=[ast.Name(id='dhash_html', ctx=ast.Store())], value=ast.Constant(''))
            return node
    files['training/data/grouping_render.py'] = ast.unparse(ast.fix_missing_locations(BeforeGlobalDhash().visit(old)))
    assignment.value = ast.parse(repr(files), mode='eval').body
    previous_pipeline = compile(ast.fix_missing_locations(tree), '<previous-notebook>', 'exec')
    work = tmp_path/'runtime'; work.mkdir()
    monkeypatch.syspath_prepend(str(work/'pipeline'))
    for name in ('scripts.supsign_training', 'scripts.dataset_eda', 'scripts.colab_downloads', 'scripts'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    clear_embedded_modules(monkeypatch)
    context = dict(WORK=work, sys=sys, GROUPS_CSV=None, SEED=42, FRAME_BLOCK_SIZE=2, NEAR_HASH_DISTANCE=None)
    exec(previous_pipeline, context)
    from training.data.grouping_review import write_grouping_review
    previous = write_grouping_review(root, tmp_path/'previous-review')
    assert 'dhash_review' not in previous

    # Same runtime, newly uploaded code, no manual sys.modules cleanup.
    exec(code, context)
    from training.data.grouping_review import write_grouping_review
    current = write_grouping_review(root, tmp_path/'current-review')
    assert 'dhash_review' in current, 'New notebook still executes the cached previous renderer'


def test_grouping_requires_current_pipeline_before_starting_review(monkeypatch):
    import builtins
    import pytest
    from training.notebooks import build_eda_notebook
    code = next(''.join(c['source']) for c in build_eda_notebook()['cells'] if c['id'] == 'grouping')
    real_import = builtins.__import__
    def no_materialized_package(name, *args, **kwargs):
        if name == 'training' or name.startswith('training.'):
            raise ModuleNotFoundError('Fresh Colab runtime has no materialized training package')
        return real_import(name, *args, **kwargs)
    with monkeypatch.context() as scoped:
        scoped.setattr(builtins, '__import__', no_materialized_package)
        with pytest.raises(AssertionError, match='pipeline'):
            exec(code, {})
