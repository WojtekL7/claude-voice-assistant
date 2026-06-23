"""Schematy Pydantic (wejście/wyjście API)."""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field


# ---------- Licencje: wejście od apki (zgodne z license_manager.py) ----------

class TrialRequest(BaseModel):
    email: EmailStr
    device_id: str
    platform: Optional[str] = None
    app_version: Optional[str] = None


class ActivateRequest(BaseModel):
    license_key: str
    device_id: str
    email: Optional[str] = ""
    platform: Optional[str] = None


class ValidateRequest(BaseModel):
    license_key: str
    device_id: str


# ---------- Pobrania ----------

class DownloadTrack(BaseModel):
    version: Optional[str] = None
    platform: Optional[str] = None
    country: Optional[str] = None


# ---------- Admin: licencje ----------

class LicenseCreate(BaseModel):
    email: EmailStr
    plan: str = "pro"                      # pro / lifetime / free
    duration_days: Optional[int] = 365     # None lub 0 => bez wygaśnięcia (np. lifetime)
    max_devices: int = 3
    notes: Optional[str] = None


class DeviceOut(BaseModel):
    device_id: str
    platform: Optional[str]
    first_seen: datetime
    last_seen: datetime

    class Config:
        from_attributes = True


class LicenseOut(BaseModel):
    id: str
    license_key: str
    email: str
    plan: str
    status: str
    max_devices: int
    trial_start: Optional[datetime]
    expires_at: Optional[datetime]
    payment_provider: Optional[str]
    payment_ref: Optional[str]
    notes: Optional[str]
    created_at: datetime
    devices: List[DeviceOut] = []

    class Config:
        from_attributes = True


# ---------- Admin: wersje ----------

class VersionCreate(BaseModel):
    version: str
    platform: str
    url: Optional[str] = None
    sha256: Optional[str] = None
    size: Optional[int] = None
    notes: Optional[str] = None


class VersionOut(BaseModel):
    id: str
    version: str
    platform: str
    url: Optional[str]
    sha256: Optional[str]
    size: Optional[int]
    notes: Optional[str]
    published_at: datetime

    class Config:
        from_attributes = True


# ---------- Admin: statystyki pobrań ----------

class DownloadStatRow(BaseModel):
    key: str
    count: int


class DownloadStats(BaseModel):
    total: int
    by_platform: List[DownloadStatRow]
    by_version: List[DownloadStatRow]
    by_day: List[DownloadStatRow]
