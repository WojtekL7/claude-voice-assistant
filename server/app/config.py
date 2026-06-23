"""Konfiguracja serwisu (z env / .env). Wszystkie sekrety przez zmienne
środowiskowe — nic nie hardcodujemy."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Połączenie do bazy. Lokalnie docker-compose ustawia host 'db'.
    database_url: str = "postgresql+psycopg://cva:cva@localhost:5432/cva"

    # Token admina (Bearer) do endpointów /api/admin/*. ZMIEŃ w produkcji.
    admin_token: str = "dev-admin-token"

    # Polityka triala i urządzeń.
    trial_days: int = 30
    default_max_devices: int = 3

    # Sól do haszowania IP przy liczeniu pobrań (prywatność — nie trzymamy IP).
    ip_hash_salt: str = "dev-salt"

    # CORS dla panelu (frontend z cloud.co.design). Lista po przecinku albo '*'.
    cors_origins: str = "*"


settings = Settings()
