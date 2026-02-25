"""
Claude Voice Assistant - License Manager
Handles trial period, license validation, and activation.
"""
import json
import hashlib
import platform
import uuid
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from enum import Enum

import requests


class LicenseStatus(Enum):
    VALID = "valid"
    TRIAL = "trial"
    TRIAL_EXPIRED = "trial_expired"
    EXPIRED = "expired"
    INVALID = "invalid"
    NO_LICENSE = "no_license"
    OFFLINE = "offline"


class LicenseManager:
    """
    Manages application licensing with trial support.
    Communicates with license server for validation.
    """

    def __init__(
        self,
        license_server_url: str = "https://license.srv1251441.hstgr.cloud/api",
        trial_days: int = 30,
        config_dir: Optional[Path] = None
    ):
        self.server_url = license_server_url
        self.trial_days = trial_days

        # Config directory
        if config_dir:
            self.config_dir = config_dir
        else:
            self.config_dir = Path.home() / ".claude-voice-assistant"

        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.license_file = self.config_dir / "license.json"
        self.device_file = self.config_dir / "device.json"

        # Current state
        self._license_data: Dict[str, Any] = {}
        self._device_id: str = ""
        self._status = LicenseStatus.NO_LICENSE

        # Load existing data
        self._load_device_id()
        self._load_license()

    def _load_device_id(self):
        """Load or generate device ID."""
        if self.device_file.exists():
            try:
                with open(self.device_file, 'r') as f:
                    data = json.load(f)
                    self._device_id = data.get('device_id', '')
            except:
                pass

        if not self._device_id:
            self._device_id = self._generate_device_id()
            self._save_device_id()

    def _save_device_id(self):
        """Save device ID to file."""
        with open(self.device_file, 'w') as f:
            json.dump({'device_id': self._device_id}, f)

    def _generate_device_id(self) -> str:
        """Generate unique device identifier."""
        # Combine various system info for uniqueness
        info = [
            platform.node(),
            platform.machine(),
            platform.processor(),
            str(uuid.getnode()),  # MAC address
        ]

        combined = '|'.join(info)
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _load_license(self):
        """Load license data from file."""
        if self.license_file.exists():
            try:
                with open(self.license_file, 'r') as f:
                    self._license_data = json.load(f)
            except:
                self._license_data = {}

    def _save_license(self):
        """Save license data to file."""
        with open(self.license_file, 'w') as f:
            json.dump(self._license_data, f, indent=2, default=str)

    def get_status(self) -> LicenseStatus:
        """Get current license status."""
        return self._status

    def get_device_id(self) -> str:
        """Get device ID."""
        return self._device_id

    def get_email(self) -> Optional[str]:
        """Get registered email."""
        return self._license_data.get('email')

    def get_trial_days_left(self) -> int:
        """Get remaining trial days."""
        if 'trial_start' not in self._license_data:
            return self.trial_days

        trial_start = datetime.fromisoformat(self._license_data['trial_start'])
        trial_end = trial_start + timedelta(days=self.trial_days)
        remaining = (trial_end - datetime.now()).days

        return max(0, remaining)

    def get_expiry_date(self) -> Optional[datetime]:
        """Get license expiry date."""
        if 'expiry_date' in self._license_data:
            return datetime.fromisoformat(self._license_data['expiry_date'])
        return None

    def start_trial(self, email: str) -> bool:
        """Start trial period."""
        try:
            # Register with server
            response = requests.post(
                f"{self.server_url}/license/trial",
                json={
                    'email': email,
                    'device_id': self._device_id,
                    'platform': platform.system(),
                    'app_version': '1.0.0'
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self._license_data = {
                    'email': email,
                    'trial_start': datetime.now().isoformat(),
                    'license_type': 'trial',
                    'server_response': data
                }
                self._save_license()
                self._status = LicenseStatus.TRIAL
                return True
            else:
                # Offline fallback - start local trial
                self._license_data = {
                    'email': email,
                    'trial_start': datetime.now().isoformat(),
                    'license_type': 'trial_offline'
                }
                self._save_license()
                self._status = LicenseStatus.TRIAL
                return True

        except requests.RequestException:
            # Offline fallback
            self._license_data = {
                'email': email,
                'trial_start': datetime.now().isoformat(),
                'license_type': 'trial_offline'
            }
            self._save_license()
            self._status = LicenseStatus.TRIAL
            return True

    def activate_license(self, license_key: str) -> tuple[bool, str]:
        """Activate license with key."""
        try:
            response = requests.post(
                f"{self.server_url}/license/activate",
                json={
                    'license_key': license_key,
                    'device_id': self._device_id,
                    'email': self._license_data.get('email', ''),
                    'platform': platform.system()
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self._license_data.update({
                    'license_key': license_key,
                    'license_type': data.get('license_type', 'pro'),
                    'expiry_date': data.get('expiry_date'),
                    'activated_at': datetime.now().isoformat()
                })
                self._save_license()
                self._status = LicenseStatus.VALID
                return True, "Licencja aktywowana pomyślnie!"
            else:
                error = response.json().get('error', 'Nieznany błąd')
                return False, f"Błąd aktywacji: {error}"

        except requests.RequestException as e:
            return False, f"Błąd połączenia: {str(e)}"

    def validate(self) -> LicenseStatus:
        """Validate current license status."""
        # Check if we have any license data
        if not self._license_data:
            self._status = LicenseStatus.NO_LICENSE
            return self._status

        license_type = self._license_data.get('license_type', '')

        # Check trial
        if license_type in ['trial', 'trial_offline']:
            days_left = self.get_trial_days_left()
            if days_left > 0:
                self._status = LicenseStatus.TRIAL
            else:
                self._status = LicenseStatus.TRIAL_EXPIRED
            return self._status

        # Check paid license
        if license_type in ['pro', 'lifetime']:
            # Try to validate with server
            try:
                response = requests.post(
                    f"{self.server_url}/license/validate",
                    json={
                        'license_key': self._license_data.get('license_key', ''),
                        'device_id': self._device_id
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get('valid'):
                        self._license_data['expiry_date'] = data.get('expiry_date')
                        self._save_license()

                        # Check expiry
                        expiry = self.get_expiry_date()
                        if expiry and expiry < datetime.now():
                            self._status = LicenseStatus.EXPIRED
                        else:
                            self._status = LicenseStatus.VALID
                    else:
                        self._status = LicenseStatus.INVALID
                else:
                    # Server error - use cached data
                    self._status = LicenseStatus.OFFLINE

            except requests.RequestException:
                # Offline - use cached validation
                expiry = self.get_expiry_date()
                if expiry:
                    if expiry < datetime.now():
                        self._status = LicenseStatus.EXPIRED
                    else:
                        self._status = LicenseStatus.OFFLINE
                else:
                    self._status = LicenseStatus.OFFLINE

            return self._status

        self._status = LicenseStatus.NO_LICENSE
        return self._status

    def can_use_app(self) -> bool:
        """Check if user can use the application."""
        status = self.validate()
        return status in [
            LicenseStatus.VALID,
            LicenseStatus.TRIAL,
            LicenseStatus.OFFLINE
        ]

    def get_purchase_url(self) -> str:
        """Get URL for purchasing license."""
        email = self._license_data.get('email', '')
        return f"{self.server_url.replace('/api', '')}/purchase?email={email}"

    def clear_license(self):
        """Clear all license data (for testing)."""
        self._license_data = {}
        if self.license_file.exists():
            self.license_file.unlink()
        self._status = LicenseStatus.NO_LICENSE
