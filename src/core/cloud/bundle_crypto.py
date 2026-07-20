"""Szyfrowanie paczki agentów — end-to-end, klucz NIGDY nie opuszcza urządzenia.

Chmura (Google Drive) jest wyłącznie magazynem bajtów: widzi szyfrogram i nic poza tym.
Decyzja usera 2026-07-20 — patrz `docs/PLAN-CHMURA-SYNC.md` sekcja 9.

Format pliku (jawny nagłówek + szyfrogram)::

    MAGIC(10B) | dł. nagłówka (4B, big-endian) | nagłówek JSON | szyfrogram

Nagłówek jest CELOWO jawny: bez zapisanych parametrów wyprowadzania klucza (sól, koszt)
nie dałoby się odszyfrować starej paczki po zmianie tych parametrów w kolejnej wersji
aplikacji. Nagłówek nie zdradza niczego wrażliwego, a jednocześnie idzie do szyfru jako
dane uwierzytelniane (AAD) → jego podmiana unieważnia odszyfrowanie.

Dobór mechanizmów:
- **AES-256-GCM** — szyfruje i JEDNOCZEŚNIE wykrywa manipulację. Podmieniony/uszkodzony
  plik z Drive'a zostanie ODRZUCONY, a nie po cichu odszyfrowany do śmieci. To istotne,
  bo paczka niesie klucze API i nadpisuje konfigurację na drugim urządzeniu.
- **scrypt** — celowo powolne i pamięciożerne wyprowadzanie klucza z hasła. Zgadywanie
  haseł staje się kosztowne (w przeciwieństwie do „szybkich" skrótów typu SHA).
  `hashlib.scrypt` jest w bibliotece standardowej; AES już nie — stąd zależność
  `cryptography` (zweryfikowana z PyInstallerem 2026-07-20).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"VCASEAL\x00\x01\x00"
FORMAT_VERSION = 1

# Koszt scrypt. n=2^15 przy r=8 to ~32 MB pamięci i ~0,1–0,3 s na współczesnym
# komputerze — nieodczuwalne przy jednym kliknięciu, a bardzo drogie przy masowym
# zgadywaniu haseł. maxmem musi być > 128*n*r, inaczej hashlib rzuci ValueError.
SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAXMEM = 256 * 1024 * 1024

KEY_BYTES = 32   # AES-256
SALT_BYTES = 16
NONCE_BYTES = 12  # zalecane dla GCM

# Alfabet kodu ratunkowego BEZ znaków mylących przy przepisywaniu z kartki
# (brak 0/O, 1/I/L). User przepisuje ręcznie — patrz pamięć `user-nietechniczny`.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


class SealError(RuntimeError):
    """Nie udało się otworzyć paczki (złe hasło, uszkodzony lub obcy plik)."""


def generate_passphrase(groups: int = 6, group_len: int = 4) -> str:
    """Mocne hasło/kod ratunkowy do zapisania na kartce (np. `A7K2-9QMX-...`).

    6 grup po 4 znaki z 31-znakowego alfabetu ≈ 119 bitów losowości — poza zasięgiem
    zgadywania, a wciąż da się to przepisać ręcznie.
    """
    return "-".join(
        "".join(secrets.choice(_CODE_ALPHABET) for _ in range(group_len))
        for _ in range(groups)
    )


def is_sealed(data: bytes) -> bool:
    """Czy bajty wyglądają na naszą zaszyfrowaną paczkę."""
    return isinstance(data, (bytes, bytearray)) and bytes(data[:len(MAGIC)]) == MAGIC


def _derive_key(passphrase: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    if not passphrase:
        raise SealError("Puste hasło — nie da się zaszyfrować ani odszyfrować paczki.")
    return hashlib.scrypt(
        passphrase.encode("utf-8"), salt=salt, n=n, r=r, p=p,
        dklen=KEY_BYTES, maxmem=SCRYPT_MAXMEM,
    )


def seal(payload: bytes, passphrase: str) -> bytes:
    """Zaszyfruj bajty paczki hasłem. Zwraca gotowy plik do wysłania do chmury."""
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    header = {
        "v": FORMAT_VERSION,
        "kdf": "scrypt",
        "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "cipher": "AES-256-GCM",
    }
    header_bytes = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    key = _derive_key(passphrase, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    # Nagłówek jako AAD: nie jest tajny, ale jego podmiana (np. podstawienie
    # słabszych parametrów) unieważni odszyfrowanie.
    ciphertext = AESGCM(key).encrypt(nonce, payload, header_bytes)
    return MAGIC + struct.pack(">I", len(header_bytes)) + header_bytes + ciphertext


def unseal(data: bytes, passphrase: str) -> bytes:
    """Odszyfruj paczkę. Złe hasło / uszkodzony plik → `SealError` (nigdy śmieci)."""
    if not is_sealed(data):
        raise SealError("To nie jest zaszyfrowana paczka Vibe Coding Assistant.")
    off = len(MAGIC)
    try:
        (header_len,) = struct.unpack(">I", data[off:off + 4])
        off += 4
        header_bytes = data[off:off + header_len]
        header = json.loads(header_bytes.decode("utf-8"))
        ciphertext = data[off + header_len:]
        salt = base64.b64decode(header["salt"])
        nonce = base64.b64decode(header["nonce"])
    except (struct.error, ValueError, KeyError, UnicodeDecodeError) as exc:
        raise SealError(f"Uszkodzony nagłówek paczki: {exc}") from exc

    if header.get("v") != FORMAT_VERSION:
        raise SealError(
            f"Paczka w nowszym formacie (wersja {header.get('v')}) — zaktualizuj aplikację.")

    key = _derive_key(passphrase, salt, header["n"], header["r"], header["p"])
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, header_bytes)
    except InvalidTag as exc:
        # GCM nie odróżnia „złe hasło" od „ktoś ruszył plik" — i dobrze, bo z punktu
        # widzenia bezpieczeństwa oba znaczą to samo: NIE ufamy tej zawartości.
        raise SealError(
            "Nie udało się otworzyć paczki: złe hasło albo plik został uszkodzony/zmieniony."
        ) from exc
