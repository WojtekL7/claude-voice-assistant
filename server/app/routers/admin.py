"""Endpointy panelu admina (/api/admin/*). Chronione tokenem (require_admin).
Zasilają makietę z cloud.co.design: Licencje, Pobrania, Wersje."""
from datetime import timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, desc
from sqlalchemy.orm import Session

from ..database import get_db
from ..security import require_admin
from ..models import License, Download, Version
from ..schemas import (
    LicenseCreate, LicenseOut, VersionCreate, VersionOut,
    DownloadStats, DownloadStatRow,
)
from ..licensing import now_utc, refresh_status

router = APIRouter(dependencies=[Depends(require_admin)])


# ---------------- Licencje ----------------

@router.get("/licenses", response_model=List[LicenseOut])
def list_licenses(
    status: Optional[str] = None,
    email: Optional[str] = None,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    stmt = select(License).order_by(desc(License.created_at)).limit(min(limit, 1000))
    if status:
        stmt = stmt.where(License.status == status)
    if email:
        stmt = stmt.where(License.email.ilike(f"%{email}%"))
    rows = list(db.scalars(stmt))
    now = now_utc()
    for lic in rows:           # odśwież status (wygaśnięcia) przy odczycie
        refresh_status(lic, now)
    db.commit()
    return rows


@router.post("/licenses", response_model=LicenseOut, status_code=201)
def create_license(payload: LicenseCreate, db: Session = Depends(get_db)):
    """Ręczne utworzenie płatnej licencji (Faza A — przed automatem płatności)."""
    expires_at = None
    if payload.duration_days and payload.duration_days > 0:
        expires_at = now_utc() + timedelta(days=payload.duration_days)
    lic = License(
        email=str(payload.email),
        plan=payload.plan,
        status="active",
        max_devices=payload.max_devices,
        expires_at=expires_at,
        notes=payload.notes,
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return lic


@router.get("/licenses/{license_id}", response_model=LicenseOut)
def get_license(license_id: str, db: Session = Depends(get_db)):
    lic = db.get(License, license_id)
    if lic is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono licencji")
    refresh_status(lic)
    db.commit()
    return lic


@router.post("/licenses/{license_id}/revoke", response_model=LicenseOut)
def revoke_license(license_id: str, db: Session = Depends(get_db)):
    lic = db.get(License, license_id)
    if lic is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono licencji")
    lic.status = "revoked"
    db.commit()
    db.refresh(lic)
    return lic


# ---------------- Pobrania (statystyki) ----------------

@router.get("/downloads/stats", response_model=DownloadStats)
def download_stats(days: int = 30, db: Session = Depends(get_db)):
    since = now_utc() - timedelta(days=max(days, 1))

    total = db.scalar(
        select(func.count()).select_from(Download).where(Download.created_at >= since)
    ) or 0

    def grouped(col):
        rows = db.execute(
            select(col, func.count())
            .where(Download.created_at >= since)
            .group_by(col)
            .order_by(desc(func.count()))
        ).all()
        return [DownloadStatRow(key=str(k) if k is not None else "?", count=c) for k, c in rows]

    by_day_rows = db.execute(
        select(func.date(Download.created_at), func.count())
        .where(Download.created_at >= since)
        .group_by(func.date(Download.created_at))
        .order_by(func.date(Download.created_at))
    ).all()
    by_day = [DownloadStatRow(key=str(d), count=c) for d, c in by_day_rows]

    return DownloadStats(
        total=total,
        by_platform=grouped(Download.platform),
        by_version=grouped(Download.version),
        by_day=by_day,
    )


# ---------------- Wersje ----------------

@router.get("/versions", response_model=List[VersionOut])
def list_versions(db: Session = Depends(get_db)):
    return list(db.scalars(select(Version).order_by(desc(Version.published_at))))


@router.post("/versions", response_model=VersionOut, status_code=201)
def create_version(payload: VersionCreate, db: Session = Depends(get_db)):
    v = Version(**payload.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return v
