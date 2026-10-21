"""Small, validated configuration shared by the API and local management commands."""

import os
import math
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    session_minutes: int = 480
    remember_days: int = 30
    auto_migrate: bool = True
    storage_root: Path = field(default_factory=lambda: PROJECT_ROOT / "backend" / "uploads" / "images")
    max_upload_bytes: int = 10 * 1024 * 1024
    max_image_pixels: int = 16_000_000
    confirmation_days: int = 30
    yolo_weights: Path = field(default_factory=lambda: PROJECT_ROOT / "ai_engine" / "checkpoints" / "detection" / "best.pt")
    yolo_device: str | None = None
    yolo_confidence: float = 0.65
    routing_base_url: str = 'https://router.project-osrm.org'
    places_provider: str = 'photon'
    places_base_url: str | None = None
    provider_user_agent: str = 'SignSight-Research/1.2'
    lifecycle_interval_seconds: int = 60
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8080", "http://127.0.0.1:8080",
    )

    def __post_init__(self):
        from urllib.parse import urlparse
        if self.places_provider not in {'photon', 'nominatim'}:
            raise ValueError('Unknown places provider; choose photon or nominatim')
        if self.places_base_url is None:
            object.__setattr__(self, 'places_base_url', 'https://photon.komoot.io' if self.places_provider == 'photon'
                               else 'https://nominatim.openstreetmap.org')
        if not math.isfinite(self.yolo_confidence) or not 0 < self.yolo_confidence <= 1:
            raise ValueError("YOLO confidence must be finite and greater than 0, up to 1")
        for url in (self.routing_base_url,self.places_base_url):
            parsed=urlparse(url)
            if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError('Provider URL must be an explicit HTTP(S) base URL')
        if not 1 <= self.lifecycle_interval_seconds <= 86400:
            raise ValueError('Lifecycle interval must be 1..86400 seconds')
        object.__setattr__(self, "storage_root", Path(self.storage_root).resolve())
        object.__setattr__(self, "yolo_weights", Path(self.yolo_weights).resolve())
        if not 1024 <= self.max_upload_bytes <= 50 * 1024 * 1024:
            raise ValueError("Upload limit must be between 1 KiB and 50 MiB")
        if not 1 <= self.max_image_pixels <= 40_000_000:
            raise ValueError("Image pixel limit must be between 1 and 40 million")
        if not 1 <= self.confirmation_days <= 365:
            raise ValueError("Confirmation period must be between 1 and 365 days")
        if not 1 <= self.session_minutes <= 1440:
            raise ValueError("SIGNSIGHT_SESSION_MINUTES must be between 1 and 1440")
        if not 1 <= self.remember_days <= 90:
            raise ValueError('SIGNSIGHT_REMEMBER_DAYS must be between 1 and 90')
        if any(origin in {"*", "null"} for origin in self.cors_origins):
            raise ValueError("CORS origins must be explicit HTTP(S) origins")
        if any(not origin.startswith(("http://", "https://")) for origin in self.cors_origins):
            raise ValueError("CORS origins must use HTTP or HTTPS")

    @classmethod
    def from_env(cls):
        auto_migrate = os.getenv("SIGNSIGHT_AUTO_MIGRATE", "true").lower()
        if auto_migrate not in {"true", "false"}:
            raise ValueError("SIGNSIGHT_AUTO_MIGRATE must be true or false")
        origins = os.getenv("SIGNSIGHT_CORS_ORIGINS")
        kwargs = {
            "session_minutes": int(os.getenv("SIGNSIGHT_SESSION_MINUTES", "480")),
            "remember_days": int(os.getenv('SIGNSIGHT_REMEMBER_DAYS', '30')),
            "auto_migrate": auto_migrate == "true",
            # A pre-existing custom endpoint used the Nominatim API contract.
            "places_provider": os.getenv('SIGNSIGHT_PLACES_PROVIDER',
                                         'nominatim' if os.getenv('SIGNSIGHT_PLACES_BASE_URL') is not None else 'photon'),
        }
        if origins is not None:
            kwargs["cors_origins"] = tuple(origin.strip().rstrip("/") for origin in origins.split(",") if origin.strip())
        for env_key, field_name, cast in (
            ("SIGNSIGHT_STORAGE_ROOT", "storage_root", Path),
            ("SIGNSIGHT_MAX_UPLOAD_BYTES", "max_upload_bytes", int),
            ("SIGNSIGHT_MAX_IMAGE_PIXELS", "max_image_pixels", int),
            ("SIGNSIGHT_CONFIRMATION_DAYS", "confirmation_days", int),
            ("SIGNSIGHT_YOLO_WEIGHTS", "yolo_weights", Path),
            ("SIGNSIGHT_YOLO_DEVICE", "yolo_device", str),
            ("SIGNSIGHT_YOLO_CONFIDENCE", "yolo_confidence", float),
            ('SIGNSIGHT_ROUTING_BASE_URL','routing_base_url',str),
            ('SIGNSIGHT_PLACES_BASE_URL','places_base_url',str),
            ('SIGNSIGHT_PROVIDER_USER_AGENT','provider_user_agent',str),
            ('SIGNSIGHT_LIFECYCLE_INTERVAL_SECONDS','lifecycle_interval_seconds',int),
        ):
            if os.getenv(env_key) is not None:
                kwargs[field_name] = cast(os.environ[env_key])
        return cls(**kwargs)
