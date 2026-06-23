"""Publiczne endpointy licencji — wołane przez apkę (license_manager.py).
Ścieżki finalne: /api/license/trial , /api/license/activate , /api/license/validate
(prefiks /api/license nadaje main.py). Formaty odpowiedzi DOKŁADNIE pod
license_manager.py: błędy zwracają {'error': ...} (nie {'detail': ...})."""
from datetime import timedelta

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import settings
from ..models import License
from ..schemas import TrialRequest, ActivateRequest, ValidateRequest
from ..licensing import now_utc, refresh_status, register_device

router = APIRouter()


@router.post("/trial")
def start_trial(payload: TrialRequest, db: Session = Depends(get_db)):
    """Rozpocznij (lub zwróć istniejący) trial dla danego emaila. Jeden trial na email."""
    now = now_utc()
    lic = db.scalar(
        select(License).where(License.email == payload.email, License.plan == "trial")
    )
    if lic is None:
        lic = License(
            email=str(payload.email),
            plan="trial",
            status="trial",
            trial_start=now,
            expires_at=now + timedelta(days=settings.trial_days),
            max_devices=settings.default_max_devices,
        )
        db.add(lic)
        db.flush()  # nadaje id/license_key
    register_device(db, lic, payload.device_id, payload.platform)
    refresh_status(lic, now)
    db.commit()
    return {
        "license_key": lic.license_key,
        "license_type": "trial",
        "status": lic.status,
        "expiry_date": lic.expires_at.isoformat() if lic.expires_at else None,
    }


@router.post("/activate")
def activate(payload: ActivateRequest, db: Session = Depends(get_db)):
    """Aktywuj płatną licencję kluczem na tym urządzeniu."""
    lic = db.scalar(select(License).where(License.license_key == payload.license_key))
    if lic is None:
        return JSONResponse(status_code=400, content={"error": "Nieprawidłowy klucz licencji"})

    now = now_utc()
    if lic.status == "revoked":
        return JSONResponse(status_code=400, content={"error": "Licencja została odwołana"})
    refresh_status(lic, now)
    if lic.status == "expired":
        db.commit()
        return JSONResponse(status_code=400, content={"error": "Licencja wygasła"})

    if not register_device(db, lic, payload.device_id, payload.platform):
        return JSONResponse(status_code=400, content={"error": "Przekroczono limit urządzeń"})

    db.commit()
    return {
        "license_type": lic.plan,
        "expiry_date": lic.expires_at.isoformat() if lic.expires_at else None,
        "status": lic.status,
    }


@router.post("/validate")
def validate(payload: ValidateRequest, db: Session = Depends(get_db)):
    """Sprawdź ważność licencji dla tego urządzenia."""
    lic = db.scalar(select(License).where(License.license_key == payload.license_key))
    if lic is None:
        return {"valid": False}

    now = now_utc()
    refresh_status(lic, now)
    # urządzenie musi być zarejestrowane (aktywowane)
    device = next((d for d in lic.devices if d.device_id == payload.device_id), None)
    if device is not None:
        device.last_seen = now
    db.commit()

    valid = (lic.status in ("trial", "active")) and (device is not None)
    return {
        "valid": valid,
        "status": lic.status,
        "license_type": lic.plan,
        "expiry_date": lic.expires_at.isoformat() if lic.expires_at else None,
    }
