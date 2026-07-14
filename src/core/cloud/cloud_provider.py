"""Wspólny interfejs dostawcy chmury (Drive/iCloud/OneDrive) + atrapa do testów.

Silnik paczki (`agent_bundle`) i GUI rozmawiają TYLKO z tym interfejsem — dołożenie
kolejnej chmury = nowa implementacja `CloudProvider`, bez zmian w reszcie kodu.
Nazwa paczki (`name`) to logiczny identyfikator w magazynie (np. "brain.vcabundle").
"""
from __future__ import annotations

import abc
from typing import Dict, List


class CloudProvider(abc.ABC):
    """Minimalny kontrakt magazynu w chmurze dla paczek 'mózgu' agenta."""

    @abc.abstractmethod
    def auth(self) -> None:
        """Zaloguj / odśwież dostęp. Rzuca wyjątek przy niepowodzeniu."""

    @abc.abstractmethod
    def upload(self, name: str, data: bytes) -> None:
        """Wgraj (nadpisz) paczkę pod nazwą `name`."""

    @abc.abstractmethod
    def download(self, name: str) -> bytes:
        """Pobierz paczkę `name`. Rzuca `KeyError`, gdy nie istnieje."""

    @abc.abstractmethod
    def list(self) -> List[str]:
        """Nazwy paczek dostępnych w chmurze (posortowane)."""

    @abc.abstractmethod
    def delete(self, name: str) -> None:
        """Usuń paczkę `name` (idempotentnie — brak = brak błędu)."""


class InMemoryProvider(CloudProvider):
    """Atrapa magazynu w pamięci — do testów silnika BEZ sieci."""

    def __init__(self) -> None:
        self._store: Dict[str, bytes] = {}
        self.authed = False

    def auth(self) -> None:
        self.authed = True

    def upload(self, name: str, data: bytes) -> None:
        self._store[name] = bytes(data)

    def download(self, name: str) -> bytes:
        if name not in self._store:
            raise KeyError(name)
        return self._store[name]

    def list(self) -> List[str]:
        return sorted(self._store)

    def delete(self, name: str) -> None:
        self._store.pop(name, None)
