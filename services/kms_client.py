import base64
import threading
from typing import Any

import requests


class SKLMError(RuntimeError):
    """Raised when Secure File cannot complete an operation through SKLM."""


class SKLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str | None,
        password: str | None,
        verify_tls: bool = True,
        connect_timeout: float = 3.0,
        read_timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.verify_tls = verify_tls
        self.timeout = (connect_timeout, read_timeout)
        self._session = requests.Session()
        self._access_token: str | None = None
        self._auth_lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    def _json(self, response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise SKLMError("SKLM returned a non-JSON response") from exc
        if not isinstance(payload, dict):
            raise SKLMError("SKLM returned an invalid response")
        return payload

    def _authenticate(self, *, force: bool = False) -> None:
        if not self.configured:
            raise SKLMError("SKLM service credentials are not configured")

        with self._auth_lock:
            if self._access_token and not force:
                return

            try:
                response = self._session.post(
                    f"{self.base_url}/api/auth/login",
                    json={"username": self.username, "password": self.password},
                    timeout=self.timeout,
                    verify=self.verify_tls,
                )
            except requests.RequestException as exc:
                raise SKLMError("Unable to connect to SKLM") from exc

            if response.status_code != 200:
                raise SKLMError(f"SKLM authentication failed ({response.status_code})")

            payload = self._json(response)
            token = payload.get("data", {}).get("access_token")
            if not token:
                raise SKLMError("SKLM login response did not contain an access token")
            self._access_token = token

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        self._authenticate()
        headers = dict(kwargs.pop("headers", {}))
        headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            response = self._session.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_tls,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise SKLMError("Unable to connect to SKLM") from exc

        if response.status_code == 401:
            self._authenticate(force=True)
            headers["Authorization"] = f"Bearer {self._access_token}"
            try:
                response = self._session.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    timeout=self.timeout,
                    verify=self.verify_tls,
                    **kwargs,
                )
            except requests.RequestException as exc:
                raise SKLMError("Unable to connect to SKLM") from exc

        return response

    def health(self) -> bool:
        try:
            response = self._session.get(
                f"{self.base_url}/health",
                timeout=self.timeout,
                verify=self.verify_tls,
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def get_key(self, key_ref: str) -> dict[str, Any]:
        response = self._request("GET", f"/api/keys/{key_ref}")
        if response.status_code != 200:
            raise SKLMError(f"Unable to read KEK metadata from SKLM ({response.status_code})")
        return self._json(response).get("data", {})

    def wrap_key(self, *, kek_ref: str, key_material: bytes) -> dict[str, Any]:
        response = self._request(
            "POST",
            "/api/crypto/wrap",
            json={
                "kek_ref": kek_ref,
                "key_material_b64": base64.b64encode(key_material).decode("ascii"),
            },
        )
        if response.status_code != 200:
            raise SKLMError(f"SKLM key-wrap operation failed ({response.status_code})")
        data = self._json(response).get("data", {})
        if not data.get("wrapped_key_b64") or not data.get("kek_version"):
            raise SKLMError("SKLM key-wrap response was incomplete")
        return data

    def unwrap_key(
        self,
        *,
        kek_ref: str,
        kek_version: int,
        wrapped_key_b64: str,
    ) -> bytes:
        response = self._request(
            "POST",
            "/api/crypto/unwrap",
            json={
                "kek_ref": kek_ref,
                "kek_version": kek_version,
                "wrapped_key_b64": wrapped_key_b64,
            },
        )
        if response.status_code != 200:
            raise SKLMError(f"SKLM key-unwrap operation failed ({response.status_code})")
        material_b64 = self._json(response).get("data", {}).get("key_material_b64")
        if not material_b64:
            raise SKLMError("SKLM key-unwrap response was incomplete")
        try:
            return base64.b64decode(material_b64, validate=True)
        except ValueError as exc:
            raise SKLMError("SKLM returned invalid key material") from exc
