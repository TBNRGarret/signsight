"""Measure the installed detector and local HTTP API using disposable demo data.

Run with the YOLO environment: python -m scripts.benchmark_demo --help.
No production database, credentials, uploads or running server are used.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
from importlib import metadata
import json
import math
from pathlib import Path
import platform
import secrets
import socket
import statistics
import tempfile
from threading import Thread
from time import monotonic, perf_counter, sleep

ROOT = Path(__file__).resolve().parents[1]


def summarize_ms(values):
    values = list(values)
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError('Latencies must be non-empty, finite and nonnegative')
    ordered = sorted(values)

    def percentile(fraction):
        position = (len(ordered) - 1) * fraction
        lower, upper = math.floor(position), math.ceil(position)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {
        'count': len(values), 'min_ms': min(values), 'mean_ms': statistics.mean(values),
        'p50_ms': percentile(.5), 'p95_ms': percentile(.95), 'max_ms': max(values),
        'samples_ms': values,
    }


def measure_ms(operation, *, samples, warmup, synchronize=lambda: None, clock=perf_counter):
    if samples < 1 or warmup < 1:
        raise ValueError('At least one sample and one warmup are required')
    for _ in range(warmup):
        synchronize()
        operation()
        synchronize()
    timings = []
    for _ in range(samples):
        synchronize()
        started = clock()
        operation()
        synchronize()
        timings.append((clock() - started) * 1000)
    return timings


def device_argument(value):
    if value != 'cpu' and not value.isdigit():
        raise argparse.ArgumentTypeError('Use cpu or a single CUDA index such as 0')
    return value


def runtime_metadata(device):
    import torch
    if device != 'cpu' and (not torch.cuda.is_available() or int(device) >= torch.cuda.device_count()):
        raise ValueError(f'CUDA device {device} is unavailable; use --device cpu')
    result = {
        'python': platform.python_version(), 'os': platform.platform(),
        'cpu': platform.processor(), 'torch': torch.__version__,
        'ultralytics': metadata.version('ultralytics'), 'uvicorn': metadata.version('uvicorn'),
        'cpu_threads': torch.get_num_threads(), 'cuda_available': torch.cuda.is_available(),
        'cuda_runtime': torch.version.cuda, 'requested_device': device,
    }
    if device != 'cpu':
        properties = torch.cuda.get_device_properties(int(device))
        result.update(gpu=properties.name, gpu_memory_bytes=properties.total_memory)
    return result


def effective_model_metadata(detector):
    model = getattr(detector, '_model', None)
    if model is None:
        return None
    # Ultralytics can retain CPU weights while a separate predictor runs on CUDA.
    try:
        parameter = next(model.predictor.model.model.parameters())
    except (AttributeError, StopIteration):
        raise RuntimeError('Device verification requires a PyTorch .pt checkpoint') from None
    return {'effective_device': str(parameter.device), 'precision': str(parameter.dtype)}


@contextmanager
def isolated_server(settings, directory):
    import uvicorn
    from backend.app.db.database import make_engine
    from backend.app.main import create_app

    engine = make_engine(f'sqlite:///{(directory / "demo.sqlite3").as_posix()}')
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    thread, server = None, None
    try:
        # Hold the socket from allocation through startup; avoid a free-port race.
        listener.bind(('127.0.0.1', 0))
        address = f'http://127.0.0.1:{listener.getsockname()[1]}'
        app = create_app(engine, settings)
        server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False, lifespan='on', ws='none'))
        thread = Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
        thread.start()
        deadline = monotonic() + 30
        while not server.started:
            if not thread.is_alive() or monotonic() >= deadline:
                raise RuntimeError('Temporary benchmark server did not start')
            sleep(.02)
        yield app, address
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=30)
            if thread.is_alive():
                raise RuntimeError('Temporary benchmark server did not shut down')
        listener.close()
        engine.dispose()


def seed_map(app):
    from ai_engine.config import CLASS_MAPPING
    from backend.app.db.models import SignRecord
    with app.state.session_factory() as db:
        for index in range(5):
            info = CLASS_MAPPING[index]
            db.add(SignRecord(
                predicted_class=index, qcvn_code=info['qcvn_code'], name_vi=info['name_vi'], confidence=.95,
                latitude=10.7769 + index * .001, longitude=106.7009,
                confirmation_days=30, status='active', verification_status='current',
                expires_at=datetime.utcnow() + timedelta(days=30),
            ))
        db.commit()


def require_response(response, expected):
    if response.status_code != expected:
        # Do not expose request credentials, session tokens or arbitrary response bodies.
        raise RuntimeError(f'Benchmark request {response.request.url.path} returned HTTP {response.status_code}')
    return response.json()


def run_benchmark(image_paths, *, weights, device, samples, warmup, confidence,catalog_path=None,mapping_path=None):
    import httpx
    from PIL import Image
    from ai_engine.detection import checkpoint_hash
    from backend.app.core.settings import Settings
    from ai_engine.catalog import SignCatalog,ModelClassMapping

    if samples < 1 or warmup < 1:
        raise ValueError('At least one sample and one warmup are required')
    device_argument(device)
    weights = Path(weights).resolve()
    expected_version = checkpoint_hash(weights)
    catalog=SignCatalog.from_file(catalog_path)
    mapping=ModelClassMapping(json.loads(Path(mapping_path).read_text(encoding='utf-8-sig')),catalog,weights) if mapping_path else None
    if not image_paths:
        raise ValueError('Provide at least one image')
    inputs = []
    for path in image_paths:
        path = Path(path)
        content = path.read_bytes()
        with Image.open(path) as image:
            media_type = Image.MIME.get(image.format, 'application/octet-stream')
        inputs.append((path, content, media_type))

    runtime = runtime_metadata(device)
    synchronize = lambda: None
    if device != 'cpu':
        import torch
        synchronize = lambda: torch.cuda.synchronize(int(device))
    report = {
        'schema_version': 1, 'measured_at_utc': datetime.now(timezone.utc).isoformat(),
        'transport': 'loopback_http', 'runtime': runtime,
        'scope': {'database': 'temporary', 'map_seed_signs': 5, 'concurrency': 1,
                  'samples_per_stage': samples, 'warmup_per_stage': warmup,
                  'excluded': ['Wi-Fi/WAN', 'HTTPS', 'browser rendering', 'camera/GPS',
                               'OSM tiles', 'Nominatim/OSRM network', 'detection quality']},
        'model': {'weights_file': weights.name, 'version': expected_version, 'confidence': confidence,
                  'catalog_sha256':catalog.sha256,'mapping_sha256':mapping.sha256 if mapping else None,
                  'nms_iou': .45, 'max_detections': 25, 'image_size_source': 'YoloDetector defaults'},
        'images': [],
    }
    with tempfile.TemporaryDirectory(prefix='signsight-benchmark-') as temporary:
        directory = Path(temporary)
        settings = Settings(storage_root=directory / 'images', yolo_weights=weights,
                            yolo_device=device, yolo_confidence=confidence,catalog_path=catalog_path,yolo_mapping_path=mapping_path)
        with isolated_server(settings, directory) as (app, address):
            seed_map(app)
            with httpx.Client(base_url=address, timeout=120, trust_env=False) as client:
                temporary_account = {'username': 'benchmark_user', 'email': 'benchmark@example.com',
                                     'password': secrets.token_urlsafe(24) + 'Aa1!'}
                require_response(client.post('/api/v1/auth/register', json=temporary_account), 201)
                login_payload = {key: temporary_account[key] for key in ('username', 'password')}
                token = require_response(client.post('/api/v1/auth/login', json=login_payload), 200)['access_token']
                client.headers['Authorization'] = 'Bearer ' + token
                started = perf_counter()
                status = app.state.detector.status()
                report['model_load_ms'] = (perf_counter() - started) * 1000
                if not status['ready']:
                    raise RuntimeError('YOLO checkpoint unavailable: ' + str(status['reason']))
                if status['model_version'] != expected_version:
                    raise RuntimeError('Loaded checkpoint hash differs from the selected weights')
                for path, content, media_type in inputs:
                    def upload():
                        return require_response(client.post('/api/v1/images', files={'file': (path.name, content, media_type)}), 201)

                    started = perf_counter()
                    uploaded = upload()
                    first_upload_ms = (perf_counter() - started) * 1000
                    image_id = uploaded['id']
                    detection_counts = []

                    def detect():
                        result = require_response(client.post(f'/api/v1/images/{image_id}/detect'), 200)
                        if result['engine'] != 'yolo' or result['model_version'] != expected_version:
                            raise RuntimeError('Detect endpoint did not use the selected YOLO checkpoint')
                        detection_counts.append(len(result['detections']))
                        return result

                    synchronize()
                    started = perf_counter()
                    detect()
                    synchronize()
                    first_detect_ms = (perf_counter() - started) * 1000
                    effective = effective_model_metadata(app.state.detector)
                    if effective is not None:
                        expected_device = 'cpu' if device == 'cpu' else f'cuda:{int(device)}'
                        if effective['effective_device'] != expected_device:
                            raise RuntimeError('Detector execution device differs from requested benchmark device')
                        report['model'].update(effective)
                    detection_counts.clear()
                    detect_timings = measure_ms(detect, samples=samples, warmup=warmup, synchronize=synchronize)
                    content_response = client.get(uploaded['content_url'])
                    if content_response.status_code != 200:
                        raise RuntimeError('Uploaded benchmark image could not be read back')
                    normalized = content_response.content
                    if hashlib.sha256(normalized).hexdigest() != uploaded['sha256']:
                        raise RuntimeError('Uploaded image content hash differs from stored metadata')
                    import io
                    with Image.open(io.BytesIO(normalized)) as stored:
                        rgb_image = stored.convert('RGB')
                    try:
                        predict_timings = measure_ms(lambda: app.state.detector.predict(rgb_image),
                                                     samples=samples, warmup=warmup, synchronize=synchronize)
                    finally:
                        rgb_image.close()
                    upload_timings = measure_ms(upload, samples=samples, warmup=warmup)
                    image_report = {
                        'file': path.name, 'source_sha256': hashlib.sha256(content).hexdigest(),
                        'source_bytes': len(content), 'media_type': media_type,
                        'width': uploaded['width'], 'height': uploaded['height'],
                        'stored_bytes': uploaded['size_bytes'], 'normalized_sha256': uploaded['sha256'],
                        'first_upload_ms': first_upload_ms, 'first_detect_ms': first_detect_ms,
                        'detect_http': summarize_ms(detect_timings), 'detector_predict': summarize_ms(predict_timings),
                        'upload_http': summarize_ms(upload_timings), 'detection_counts': detection_counts[-samples:],
                    }
                    model = getattr(app.state.detector, '_model', None)
                    if model is not None:
                        image_report['configured_imgsz'] = list(model.predictor.imgsz)
                    report['images'].append(image_report)

                def map_page():
                    result = require_response(client.get('/api/v1/map/signs', params={
                        'min_lat': 10.70, 'max_lat': 10.90, 'min_lon': 106.60, 'max_lon': 106.80}), 200)
                    if result['total'] != 5:
                        raise RuntimeError('Temporary map fixtures changed during the benchmark')

                report['map_http'] = summarize_ms(measure_ms(map_page, samples=samples, warmup=warmup))
                response = client.post('/api/v1/auth/logout')
                if response.status_code != 204:
                    raise RuntimeError('Temporary benchmark session did not close')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, action='append', required=True, help='Input image; repeat to benchmark several sizes')
    parser.add_argument('--weights', type=Path, default=ROOT / 'ai_engine/checkpoints/detection/best.pt')
    parser.add_argument('--device', type=device_argument, default='cpu', help='cpu or a single CUDA index, e.g. 0')
    parser.add_argument('--samples', type=int, default=20)
    parser.add_argument('--warmup', type=int, default=3)
    parser.add_argument('--confidence', type=float, default=.65)
    parser.add_argument('--catalog',type=Path)
    parser.add_argument('--mapping',type=Path)
    parser.add_argument('--output', type=Path, required=True, help='New JSON report; existing files are never overwritten')
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('Output already exists; choose a new report filename')
    try:
        report = run_benchmark(args.image, weights=args.weights, device=args.device, samples=args.samples,
                               warmup=args.warmup, confidence=args.confidence,catalog_path=args.catalog,mapping_path=args.mapping)
        document = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as output:
            output.write(document + '\n')
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(1, f'Benchmark failed: {error}\n')
    print(f'Benchmark saved: {args.output}')
    for image in report['images']:
        stage = image['detect_http']
        print(f"{image['file']} ({image['width']}x{image['height']}): detect HTTP p50={stage['p50_ms']:.1f} ms, p95={stage['p95_ms']:.1f} ms")


if __name__ == '__main__':
    main()
