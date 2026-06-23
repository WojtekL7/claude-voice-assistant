# VCA — License / Admin API (Faza A)

Backend dla Vibe Coding Assistant: serwer licencji + API panelu administracyjnego.
FastAPI + PostgreSQL. Frontend panelu powstaje osobno (cloud.co.design → zip) i
podepniemy go pod to API.

## Co już jest (Faza A)
- **Endpointy licencji** zgodne z apką (`src/core/license_manager.py`):
  - `POST /api/license/trial` — start/zwrot triala (1 na email)
  - `POST /api/license/activate` — aktywacja płatnego klucza na urządzeniu
  - `POST /api/license/validate` — walidacja ważności
- **Pobrania:** `POST /api/downloads/track` (IP haszowane).
- **Panel (admin, Bearer token):**
  - `GET/POST /api/admin/licenses`, `GET /api/admin/licenses/{id}`, `POST /api/admin/licenses/{id}/revoke`
  - `GET /api/admin/downloads/stats?days=30`
  - `GET/POST /api/admin/versions`
- `GET /api/health` — health check. Dokumentacja interaktywna: `/docs`.

## Uruchomienie lokalne (docker-compose)
```bash
cd server
cp .env.example .env          # ustaw ADMIN_TOKEN / IP_HASH_SALT
docker compose up --build
# API: http://localhost:8088  ·  docs: http://localhost:8088/docs
# Postgres na hoście: localhost:5433 (żeby nie kolidować z lokalnym 5432)
```

## Uruchomienie bez Dockera (dev)
```bash
cd server
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="sqlite+pysqlite:///./dev.sqlite3"   # albo Postgres
export ADMIN_TOKEN="dev-admin-token"
uvicorn app.main:app --reload --port 8088
```

## Szybki test (curl)
```bash
TOKEN=dev-admin-token
# utwórz płatną licencję (panel/ręcznie):
curl -s -X POST localhost:8088/api/admin/licenses \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"email":"klient@example.com","plan":"pro","duration_days":365,"max_devices":3}'
# aktywacja w apce (symulacja):
curl -s -X POST localhost:8088/api/license/activate \
  -H 'Content-Type: application/json' \
  -d '{"license_key":"<KLUCZ_Z_POWYZSZEGO>","device_id":"dev-1","email":"klient@example.com"}'
```

## Podpięcie apki (Faza A → test)
`src/core/license_manager.py` woła już `https://license.srv1251441.hstgr.cloud/api`.
Do testu lokalnego utwórz `LicenseManager(license_server_url="http://localhost:8088/api")`.

## TODO (Faza B)
- Webhook płatności (Paddle/Stripe) → automatyczne tworzenie/odnawianie licencji.
- Sekcja Firma (dokumenty prawne `legal_docs`) + edycja w panelu.
- Bramkowanie funkcji Pro w apce (na podstawie statusu licencji).
- Migracje (Alembic) zamiast `create_all`. Rate limiting na publicznych endpointach.
- Deploy na VPS (kontener `cva-api` za Traefik, `license.srv1251441.hstgr.cloud`).
