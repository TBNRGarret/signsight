"""Resolve one user-supplied Drive ZIP. No extraction, training, or credentials."""
from pathlib import Path
import re
from time import time_ns
import zipfile


def validate_archive(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f'Không thấy ZIP: {path}. Kiểm tra đường dẫn trên Drive.')
    try:
        with zipfile.ZipFile(path) as archive:
            if not archive.infolist():
                raise ValueError('ZIP rỗng; chưa có file để EDA.')
            if any(item.flag_bits & 1 for item in archive.infolist()):
                raise ValueError('ZIP có mật khẩu; cần bản ZIP không mã hóa để đọc ảnh/nhãn.')
    except zipfile.BadZipFile as error:
        raise ValueError('File không phải ZIP hợp lệ; có thể là trang đăng nhập/quota Drive hoặc tải chưa đủ.') from error
    return path


def resolve_archive(file_id, cache_root, *, local_archive=None, download=None):
    if not isinstance(file_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', file_id):
        raise ValueError('Drive file ID không hợp lệ; chỉ điền ID, không phải URL.')
    if local_archive:
        return validate_archive(local_archive)
    directory = Path(cache_root).resolve() / file_id
    destination = directory / 'archive.zip'
    if destination.exists():
        return validate_archive(destination)
    directory.mkdir(parents=True, exist_ok=True)
    if download is None:
        import gdown
        download = gdown.download
    partial = directory / 'archive.zip.part'
    try:
        result = download(id=file_id, output=str(partial), quiet=False, resume=True, use_cookies=False)
    except Exception as error:
        raise RuntimeError('Chưa tải được file Drive. Kiểm tra quyền xem/quota hoặc dùng SOURCE_MODE="drive" để đọc file gốc qua Drive mount.') from error
    if result is None or not partial.is_file():
        raise RuntimeError('Drive chưa trả file. Dùng Drive mount nếu link cần đăng nhập hoặc đang vượt quota.')
    try:
        validate_archive(partial)
    except ValueError:
        # Quarantine a completed HTML/broken response so resume will not reuse it.
        partial.rename(directory / f'archive.invalid-{time_ns()}.download')
        raise
    # Publish only a complete ZIP. gdown owns its incomplete resume files.
    if destination.exists():
        raise FileExistsError('Cache đã xuất hiện trong lúc tải; không ghi đè.')
    partial.rename(destination)
    return destination
