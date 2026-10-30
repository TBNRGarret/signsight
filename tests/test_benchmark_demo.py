"""Benchmark statistics and real HTTP/storage isolation, with a test detector."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from scripts import benchmark_demo


def test_latency_summary_uses_interpolated_percentiles_and_retains_samples():
    summary = benchmark_demo.summarize_ms([50, 10, 40, 20, 30])
    assert summary == {
        'count': 5, 'min_ms': 10, 'mean_ms': 30, 'p50_ms': 30,
        'p95_ms': 48, 'max_ms': 50, 'samples_ms': [50, 10, 40, 20, 30],
    }


@pytest.mark.parametrize('samples', [[], [-1, 2], [float('nan')], [float('inf')]])
def test_latency_summary_rejects_empty_or_invalid_measurements(samples):
    with pytest.raises(ValueError):
        benchmark_demo.summarize_ms(samples)


def test_measure_excludes_warmups_and_waits_for_device_completion():
    calls, syncs = [], []
    times = iter([0, .010, 1, 1.020])
    samples = benchmark_demo.measure_ms(
        lambda: calls.append('request'), samples=2, warmup=3,
        synchronize=lambda: syncs.append('sync'), clock=lambda: next(times),
    )
    assert samples == pytest.approx([10, 20])
    assert len(calls) == 5
    assert len(syncs) == 10


@pytest.mark.parametrize(('samples', 'warmup'), [(0, 1), (2, 0), (-1, 2)])
def test_measure_requires_samples_and_warmup(samples, warmup):
    with pytest.raises(ValueError):
        benchmark_demo.measure_ms(lambda: None, samples=samples, warmup=warmup)


@pytest.mark.parametrize('custom_mapping',[False,True])
def test_benchmark_uses_loopback_http_temporary_db_and_real_upload_storage(tmp_path, monkeypatch,custom_mapping):
    from ai_engine.detection import DetectionResult, checkpoint_hash
    from backend.app import main as app_module

    checkpoint = tmp_path / 'test.pt'
    checkpoint.write_bytes(b'test detector weights, not a real YOLO model')
    image_path = tmp_path / 'sample.png'
    Image.new('RGB', (64, 48), 'white').save(image_path)
    database_sentinel = tmp_path / 'existing.db'
    database_sentinel.write_bytes(b'do not modify existing data')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{database_sentinel.as_posix()}')
    actual_version = checkpoint_hash(checkpoint)
    from ai_engine.catalog import SignCatalog
    from test_catalog_mapping import extended_items,mapping_data
    catalog=SignCatalog(extended_items() if custom_mapping else None)
    catalog_path=tmp_path/'catalog.json';catalog_path.write_text(json.dumps([dict(item) for item in catalog.items]))
    mapping_path=tmp_path/'mapping.json';mapping_path.write_text(json.dumps(mapping_data(catalog,checkpoint)) if custom_mapping else '{}')

    class TestDetector:
        def __init__(self, weights, device, confidence,*,catalog,mapping_path):
            assert Path(weights) == checkpoint.resolve()
            assert len(catalog.items)==(11 if custom_mapping else 10)
            assert (mapping_path is not None)==custom_mapping
            self.version = checkpoint_hash(weights)

        def status(self):
            return {'ready': True, 'reason': None, 'model_version': self.version}

        def predict(self, image):
            assert image.mode == 'RGB' and image.size == (64, 48)
            return DetectionResult(self.version, [])

    monkeypatch.setattr(app_module, 'YoloDetector', TestDetector)
    monkeypatch.setattr(benchmark_demo, 'runtime_metadata', lambda device: {'device': device, 'test_double': True})
    report = benchmark_demo.run_benchmark(
        [image_path], weights=checkpoint, device='cpu', samples=2, warmup=1, confidence=.65,
        catalog_path=catalog_path if custom_mapping else None,mapping_path=mapping_path if custom_mapping else None,
    )
    assert report['transport'] == 'loopback_http'
    assert report['scope']['database'] == 'temporary'
    assert report['scope']['map_seed_signs'] == 5
    assert report['scope']['concurrency'] == 1
    assert report['model']['version'] == actual_version
    assert report['model']['catalog_sha256']==catalog.sha256
    assert bool(report['model']['mapping_sha256'])==custom_mapping
    assert report['map_http']['count'] == 2
    image = report['images'][0]
    assert image['width'] == 64 and image['height'] == 48
    assert image['source_sha256'] == hashlib.sha256(image_path.read_bytes()).hexdigest()
    assert image['normalized_sha256'] != image['source_sha256']
    for stage in ('upload_http', 'detect_http', 'detector_predict'):
        assert image[stage]['count'] == 2
    assert image['detection_counts'] == [0, 0]
    assert database_sentinel.read_bytes() == b'do not modify existing data'
    serialized = json.dumps(report)
    for secret in ('access_token', 'Authorization', 'password', 'storage_key'):
        assert secret not in serialized


def test_benchmark_stops_on_unavailable_checkpoint_instead_of_using_cnn(tmp_path, monkeypatch):
    from backend.app import main as app_module

    image_path = tmp_path / 'sample.png'
    Image.new('RGB', (64, 48), 'white').save(image_path)
    class UnavailableDetector:
        def __init__(self, *args, **kwargs):
            pass

        def status(self):
            return {'ready': False, 'reason': 'dependencies_missing', 'model_version': None}

    weights = tmp_path / 'test.pt'
    weights.write_bytes(b'test weights')
    monkeypatch.setattr(app_module, 'YoloDetector', UnavailableDetector)
    monkeypatch.setattr(benchmark_demo, 'runtime_metadata', lambda device: {'device': device})
    with pytest.raises(RuntimeError, match='dependencies_missing'):
        benchmark_demo.run_benchmark([image_path], weights=weights, device='cpu', samples=2, warmup=1, confidence=.65)


def test_cli_refuses_to_replace_a_previous_report(tmp_path):
    output = tmp_path / 'report.json'
    output.write_text('preserve previous experiment', encoding='utf-8')
    with pytest.raises(SystemExit) as error:
        benchmark_demo.main(['--image', 'missing.png', '--output', str(output)])
    assert error.value.code != 0
    assert output.read_text(encoding='utf-8') == 'preserve previous experiment'


@pytest.mark.parametrize('actual_device', ['cpu', 'cuda:0'])
def test_device_report_reads_execution_backend_instead_of_cpu_weights_wrapper(actual_device):
    cpu_weights = SimpleNamespace(parameters=lambda: iter([SimpleNamespace(device='cpu', dtype='torch.float32')]))
    execution = SimpleNamespace(parameters=lambda: iter([SimpleNamespace(device=actual_device, dtype='torch.float32')]))
    detector = SimpleNamespace(_model=SimpleNamespace(
        model=cpu_weights, predictor=SimpleNamespace(model=SimpleNamespace(model=execution)),
    ))
    assert benchmark_demo.effective_model_metadata(detector) == {
        'effective_device': actual_device, 'precision': 'torch.float32',
    }
