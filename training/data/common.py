import hashlib, json
from pathlib import Path

CAR35 = [
    'Speed_limit_40', 'Speed_limit_50', 'Speed_limit_60', 'Speed_limit_70', 'Speed_limit_80',
    'No_entry', 'No_cars', 'No_cars_turn_left', 'No_cars_turn_right',
    'No_turn_left', 'No_turn_right', 'No_U_turn', 'No_cars_U_turn',
    'No_straight_ahead', 'No_turn_left_and_U_turn', 'No_turn_left_and_right',
    'No_parking', 'No_stopping_and_parking', 'No_parking_odd_days', 'No_parking_even_days',
    'Go_straight', 'Keep_right', 'Roundabout', 'One_way_road', 'Road_reserved_for_cars',
    'Pedestrian_crossing', 'Children_crossing', 'Road_works', 'Slow_down',
    'Dangerous_curve_left', 'Dangerous_curve_right',
    'No_overtaking', 'End_no_overtaking', 'Give_way', 'End_all_prohibitions',
]
SPLITS = ('train', 'val', 'test')
VERSION = 2


def digest_file(path):
    with Path(path).open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024*1024), b''): digest.update(block)
        return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def recipe(classes=CAR35, seed=42, block_size=100, near_threshold=4, groups=None):
    from training.compatibility import implementation_digest
    group_digest = hashlib.sha256(json.dumps(groups, sort_keys=True).encode()).hexdigest()
    return dict(version=VERSION, classes=list(classes), seed=seed, block_size=block_size,
        near_threshold=near_threshold, groups_sha256=group_digest,
        implementation_sha256=implementation_digest(),
        reader_sha256=hashlib.sha256(Path(__file__).with_name('audit.py').read_text(encoding='utf-8').encode()).hexdigest())
