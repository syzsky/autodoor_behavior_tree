import hashlib
import socket
import time
from typing import Any, Dict, Optional

import requests

from bt_utils.log_manager import LogManager


class PlatformAPIClient:
    DEFAULT_BASE_URL = "https://autodoor.lizhileyun.com"
    API_NAMESPACE = "/wp-json/bt/v1/executor"
    CONNECT_TIMEOUT = 10
    READ_TIMEOUT = 30

    def __init__(self, base_url: str = None):
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "AutoDoorEditor/1.0.0",
        })
        self._token: Optional[str] = None
        self._token_expire_time: float = 0
        self._last_error: str = ""

    def _build_url(self, endpoint: str) -> str:
        return f"{self._base_url}{self.API_NAMESPACE}{endpoint}"

    def _get_auth_headers(self) -> Dict[str, str]:
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def login(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        try:
            device_id = hashlib.md5(f"{username}_{socket.gethostname()}".encode()).hexdigest()[:16]
            device_name = f"Editor-{socket.gethostname()}"

            url = self._build_url("/request-token")
            payload = {
                "username": username,
                "password": password,
                "device_id": device_id,
                "device_name": device_name,
            }

            print(f"[Auth] 请求登录: {url}, user={username}")
            response = self._session.post(
                url,
                json=payload,
                timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT)
            )

            if response.status_code != 200:
                try:
                    err_data = response.json()
                    msg = err_data.get("message", "")
                    if not msg:
                        code = err_data.get("code", "")
                        msg = code if code else f"登录失败({response.status_code})"
                except Exception:
                    msg = f"登录失败({response.status_code})"
                self._last_error = msg
                print(f"[Auth] 登录失败: {msg} (status={response.status_code})")
                return None

            result = response.json()
            if result.get("success", False):
                data = result.get("data", {})
                token = data.get("token", data.get("session_token", ""))
                self._token = token
                self._token_expire_time = time.time() + 3600
                self._last_error = ""
                print(f"[Auth] 登录成功: {username}, token={token[:16]}...")
                return {
                    "token": token,
                    "user_id": str(data.get("user_id", "")),
                    "display_name": data.get("display_name", username),
                    "roles": data.get("roles", []),
                    "expires_in": 3600,
                }

            self._last_error = result.get("message", "登录失败")
            print(f"[Auth] 登录失败: {self._last_error}")
            return None

        except requests.RequestException as e:
            self._last_error = f"网络请求失败: {e}"
            print(f"[Auth] 登录请求异常: {e}")
            return None

    def get_last_error(self) -> str:
        return self._last_error

    def refresh_token(self, refresh_token: str) -> Optional[Dict[str, Any]]:
        try:
            response = self._session.post(
                self._build_url("/refresh-token"),
                json={"refresh_token": refresh_token},
                timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT)
            )
            response.raise_for_status()
            result = response.json()
            if result.get("success", False):
                data = result.get("data", {})
                token = data.get("token", data.get("session_token", ""))
                self._token = token
                self._token_expire_time = time.time() + 3600
                return {"token": token, "expires_in": 3600}
            return None
        except requests.RequestException as e:
            LogManager.instance().log_failure(
                node_type="PlatformAPIClient",
                node_name="refresh_token",
                reason=f"刷新令牌失败: {e}"
            )
            return None

    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        try:
            original_token = self._token
            self._token = token
            response = self._session.post(
                self._build_url("/validate-token"),
                headers=self._get_auth_headers(),
                timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT)
            )
            response.raise_for_status()
            result = response.json()
            if result.get("success", False):
                self._token_expire_time = time.time() + 3600
                return {"valid": True, "expires_in": 3600}
            return None
        except requests.RequestException as e:
            LogManager.instance().log_failure(
                node_type="PlatformAPIClient",
                node_name="validate_token",
                reason=f"验证令牌失败: {e}"
            )
            return None
        finally:
            self._token = original_token

    def get_user_info(self) -> Optional[Dict[str, Any]]:
        try:
            if not self._token:
                return None
            response = self._session.get(
                self._build_url("/user-info"),
                headers=self._get_auth_headers(),
                timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT)
            )
            response.raise_for_status()
            result = response.json()
            if result.get("success", False):
                return result.get("data", {})
            return None
        except requests.RequestException as e:
            LogManager.instance().log_failure(
                node_type="PlatformAPIClient",
                node_name="get_user_info",
                reason=f"获取用户信息失败: {e}"
            )
            return None

    def set_token(self, token: str, expire_time: float = 0) -> None:
        self._token = token
        self._token_expire_time = expire_time

    def get_token(self) -> Optional[str]:
        return self._token

    def is_token_expired(self) -> bool:
        if not self._token:
            return True
        return time.time() >= self._token_expire_time

    def logout(self) -> None:
        try:
            if self._token:
                self._session.post(
                    self._build_url("/revoke-token"),
                    headers=self._get_auth_headers(),
                    timeout=(self.CONNECT_TIMEOUT, self.READ_TIMEOUT)
                )
        except requests.RequestException:
            pass
        finally:
            self._token = None
            self._token_expire_time = 0
