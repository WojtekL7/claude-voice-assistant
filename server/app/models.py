"""Modele bazy (SQLAlchemy 2.0). Rdzeń Fazy A: licencje + urządzenia + pobrania
+ wersje + dokumenty prawne."""
import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class License(Base):
    """Licencja/subskrypcja. Trial i płatne (pro/lifetime) w jednej tabeli."""
    __tablename__ = "licenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Klucz licencji (UUID) — to nim aktywuje się płatną licencję w apce.
    license_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), index=True)
    plan: Mapped[str] = mapped_column(String(20), default="trial")    # trial / pro / lifetime / free
    status: Mapped[str] = mapped_column(String(20), default="trial")  # trial / active / expired / revoked
    max_devices: Mapped[int] = mapped_column(Integer, default=3)

    trial_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Powiązanie z płatnością (Faza B): np. 'stripe'/'paddle' + id subskrypcji.
    payment_provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    payment_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    devices: Mapped[List["Device"]] = relationship(
        back_populates="license", cascade="all, delete-orphan")


class Device(Base):
    """Aktywacja licencji na konkretnym urządzeniu (do limitu max_devices)."""
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    license_id: Mapped[str] = mapped_column(
        ForeignKey("licenses.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    platform: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    license: Mapped["License"] = relationship(back_populates="devices")


class Download(Base):
    """Zarejestrowane pobranie paczki (do statystyk). IP haszowane (prywatność)."""
    __tablename__ = "downloads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True)


class Version(Base):
    """Wydana wersja paczki (per platforma). Źródło dla appcastu/panelu Wersje."""
    __tablename__ = "versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version: Mapped[str] = mapped_column(String(20), index=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)  # macos-arm64 / windows-x64 / linux-x64
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LegalDoc(Base):
    """Dokument prawny (polityka/licencja/regulamin) z wersjonowaniem. Faza B (UI)."""
    __tablename__ = "legal_docs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    doc_type: Mapped[str] = mapped_column(String(30), index=True)  # privacy / license / terms
    lang: Mapped[str] = mapped_column(String(8), default="pl")
    version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
