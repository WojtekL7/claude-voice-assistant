"""Logika domenowa licencji wspólna dla routerów (status, rejestracja urządzeń)."""
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .models import License, Device


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    """Niektóre sterowniki (SQLite) zwracają daty bez strefy. Traktuj naive jako
    UTC, żeby porównania z now_utc() nie wywalały 'naive vs aware'."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def refresh_status(lic: License, now: datetime | None = None) -> None:
    """Przelicz status wg dat. 'revoked' jest nadrzędne (nie zmieniamy)."""
    now = now or now_utc()
    if lic.status == "revoked":
        return
    expires_at = _as_aware(lic.expires_at)
    if expires_at is not None and expires_at < now:
        lic.status = "expired"
    elif lic.plan == "trial":
        lic.status = "trial"
    else:
        lic.status = "active"


def register_device(db: Session, lic: License, device_id: str,
                    platform: str | None) -> bool:
    """Zarejestruj/odśwież urządzenie. Zwraca False, gdy przekroczono limit
    (urządzenie nowe, a licznik == max_devices)."""
    existing = db.scalar(
        select(Device).where(Device.license_id == lic.id, Device.device_id == device_id)
    )
    if existing is not None:
        existing.last_seen = now_utc()
        if platform:
            existing.platform = platform
        return True
    count = db.scalar(
        select(func.count()).select_from(Device).where(Device.license_id == lic.id)
    ) or 0
    if count >= lic.max_devices:
        return False
    db.add(Device(license_id=lic.id, device_id=device_id, platform=platform))
    return True
