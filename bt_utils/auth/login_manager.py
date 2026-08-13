import time
from typing import Optional, Dict, Any, Callable

from bt_utils.log_manager import LogManager
from .api_client import PlatformAPIClient
from .credential_store import CredentialStore


class LoginManager:
    def __init__(self, api_client: Optional[PlatformAPIClient] = None,
                 credential_store: Optional[CredentialStore] = None):
        self._api_client = api_client or PlatformAPIClient(self._load_base_url())
        self._credential_store = credential_store or CredentialStore()
        self._current_user: Optional[str] = None
        self._is_authenticated: bool = False
        self._is_offline: bool = False
        self._on_login: Optional[Callable] = None
        self._on_logout: Optional[Callable] = None

    @staticmethod
    def _load_base_url() -> str:
        """从配置读取登录服务器地址（auth.platform.base_url），未配置返回空串。

        开源仓库不包含真实服务器地址，用户需在配置中自行填写。
        """
        try:
            from config.settings_manager import SettingsManager
            return str(SettingsManager.get_instance().get(
                "auth.platform.base_url", "") or "").strip()
        except Exception:
            return ""

    def login(self, username: str, password: str, remember: bool = False) -> bool:
        result = self._api_client.login(username, password)
        if result:
            self._current_user = username
            self._is_authenticated = True
            self._is_offline = False
            if remember:
                expire_time = result.get("expire_time", 0) or \
                    (time.time() + result.get("expires_in", 3600))
                self._credential_store.save_credentials(
                    username, password,
                    token=result.get("token", ""),
                    refresh_token=result.get("refresh_token", ""),
                    expire_time=expire_time
                )
            if self._on_login:
                try:
                    self._on_login(username, result)
                except Exception as e:
                    LogManager.instance().log_failure(
                        node_type="LoginManager",
                        node_name="login_callback",
                        reason=f"登录回调异常: {e}"
                    )
            self._current_user = result.get("display_name", username)
            print(f"[Auth] 登录成功: {username} -> {self._current_user}")
            return True
        return False

    def auto_login(self) -> bool:
        try:
            if self._current_user:
                credentials = self._credential_store.get_credentials(self._current_user)
                username = self._current_user
            else:
                result = self._credential_store.get_first_credential()
                if not result:
                    return False
                username, credentials = result

            if not credentials:
                return False

            print(f"[Auth] 自动登录: user={username}")

            if credentials.get("password"):
                return self.login(username, credentials["password"])
            elif credentials.get("token"):
                if not self._credential_store.is_token_expired(username):
                    token = credentials["token"]
                    expire_time = credentials.get("expire_time", 0)
                    self._api_client.set_token(token, expire_time)
                    validation = self._api_client.validate_token(token)
                    if validation:
                        self._current_user = username
                        self._is_authenticated = True
                        self._is_offline = False
                        if self._on_login:
                            try:
                                self._on_login(username, validation)
                            except Exception:
                                pass
                        return True
                elif credentials.get("refresh_token"):
                    refreshed = self._api_client.refresh_token(credentials["refresh_token"])
                    if refreshed:
                        self._current_user = username
                        self._is_authenticated = True
                        self._is_offline = False
                        self._credential_store.save_token(
                            username,
                            token=refreshed.get("token", ""),
                            refresh_token=refreshed.get("refresh_token", ""),
                            expire_time=time.time() + refreshed.get("expires_in", 3600)
                        )
                        if self._on_login:
                            try:
                                self._on_login(username, refreshed)
                            except Exception:
                                pass
                        return True
            return False
        except Exception as e:
            LogManager.instance().log_failure(
                node_type="LoginManager",
                node_name="auto_login",
                reason=f"自动登录失败: {e}"
            )
            return False

    def try_offline_mode(self, username: str = "") -> bool:
        try:
            credentials = self._credential_store.get_credentials(username)
            if credentials and credentials.get("token"):
                self._current_user = username
                self._is_authenticated = True
                self._is_offline = True
                self._api_client.set_token(
                    credentials["token"],
                    credentials.get("expire_time", 0)
                )
                if self._on_login:
                    try:
                        self._on_login(username, {"token": credentials["token"], "offline": True})
                    except Exception:
                        pass
                return True
            return False
        except Exception:
            return False

    def logout(self) -> None:
        try:
            if self._api_client:
                self._api_client.logout()
        except Exception:
            pass
        finally:
            if self._current_user:
                self._credential_store.save_token(self._current_user, "", "", 0)
            self._current_user = None
            self._is_authenticated = False
            self._is_offline = False
            if self._on_logout:
                try:
                    self._on_logout()
                except Exception as e:
                    LogManager.instance().log_failure(
                        node_type="LoginManager",
                        node_name="logout_callback",
                        reason=f"登出回调异常: {e}"
                    )

    def is_authenticated(self) -> bool:
        return self._is_authenticated

    def is_offline(self) -> bool:
        return self._is_offline

    def get_current_user(self) -> Optional[str]:
        return self._current_user

    def get_last_error(self) -> str:
        return self._api_client.get_last_error() if self._api_client else ""

    def get_token(self) -> Optional[str]:
        return self._api_client.get_token() if self._api_client else None

    def set_on_login_callback(self, callback: Callable) -> None:
        self._on_login = callback

    def set_on_logout_callback(self, callback: Callable) -> None:
        self._on_logout = callback

    def set_api_client(self, api_client: PlatformAPIClient) -> None:
        self._api_client = api_client

    def get_api_client(self) -> PlatformAPIClient:
        return self._api_client

    def set_credential_store(self, credential_store: CredentialStore) -> None:
        self._credential_store = credential_store

    def get_credential_store(self) -> CredentialStore:
        return self._credential_store
