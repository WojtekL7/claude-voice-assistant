"""Liczenie pobrań. Publiczny endpoint /api/downloads/track — strona pobierania
albo endpoint-redirect woła go przy pobraniu. IP haszowane (nie trzymamy IP)."""
import hashlib

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import settings
from ..models import Download
from ..schemas import DownloadTrack

router = APIRouter()


@router.post("/track")
def track(payload: DownloadTrack, request: Request, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else ""
    ip_hash = None
    if ip:
        ip_hash = hashlib.sha256((settings.ip_hash_salt + ip).encode()).hexdigest()
    db.add(Download(
        version=payload.version,
        platform=payload.platform,
        country=payload.country,
        ip_hash=ip_hash,
    ))
    db.commit()
    return {"ok": True}
