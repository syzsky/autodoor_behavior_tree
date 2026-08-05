"""通用 OpenAI 兼容 API 客户端

支持任意 OpenAI 兼容 API（OpenAI / Azure / 通义千问 / 本地 Ollama 等）。
只需配置 base_url + api_key + model 即可切换模型。
"""
import json
import requests
from typing import Any, Dict, List, Optional


class LLMClientError(Exception):
    """LLM 客户端错误"""
    pass


class LLMClient:
    """通用 LLM/VLM API 客户端（OpenAI 兼容协议）"""

    def __init__(self, base_url: str, api_key: str, model: str,
                 timeout_ms: int = 30000, max_tokens: int = 4096,
                 json_mode: str = "auto"):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_ms = timeout_ms
        self.max_tokens = max_tokens
        # json_mode: "auto"（自动降级）/ "json_object"（始终启用）/ "none"（禁用）
        self.json_mode = (json_mode or "auto").lower()

    @classmethod
    def from_config(cls, config_key: str = "llm") -> "LLMClient":
        """从 SettingsManager 配置创建客户端

        Args:
            config_key: "llm" 或 "vlm"，对应 ai.llm / ai.vlm 配置段
        """
        from config.settings_manager import get_settings_manager
        sm = get_settings_manager()

        return cls(
            base_url=sm.get(f"ai.{config_key}.base_url", "https://api.openai.com/v1"),
            api_key=sm.get(f"ai.{config_key}.api_key", ""),
            model=sm.get(f"ai.{config_key}.model", "gpt-4o"),
            timeout_ms=sm.get(f"ai.{config_key}.timeout_ms", 300000),
            max_tokens=sm.get(f"ai.{config_key}.max_tokens", 4096),
            json_mode=sm.get(f"ai.{config_key}.json_mode", "auto"),
        )

    def chat(self, messages: List[Dict[str, Any]],
             temperature: float = 0.7,
             response_format: Optional[Dict] = None) -> Dict[str, Any]:
        """发送文本对话请求

        Args:
            messages: 消息列表 [{"role": "system/user/assistant", "content": "..."}]
            temperature: 温度参数
            response_format: 响应格式（如 {"type": "json_object"}）

        Returns:
            {"content": str, "model": str, "usage": dict, "raw": dict}
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": self.max_tokens,
        }
        resp_format = response_format
        # json_mode 为 "none" 时禁用 response_format
        if self.json_mode == "none":
            resp_format = None
        if resp_format:
            payload["response_format"] = resp_format

        try:
            resp = self._post("/chat/completions", payload)
        except LLMClientError as e:
            # auto 模式下，若模型不支持 json_object 则去除该参数重试一次
            if (self.json_mode == "auto" and resp_format
                    and resp_format.get("type") == "json_object"
                    and self._is_json_object_unsupported(e)):
                payload.pop("response_format", None)
                resp = self._post("/chat/completions", payload)
            else:
                raise
        choice = resp["choices"][0]
        return {
            "content": choice["message"]["content"],
            "model": resp.get("model", self.model),
            "usage": resp.get("usage", {}),
            "raw": resp,
        }

    @staticmethod
    def _is_json_object_unsupported(error: LLMClientError) -> bool:
        """判断错误是否为模型不支持 json_object"""
        msg = str(error).lower()
        return ("json_object" in msg and
                ("not supported" in msg or "not valid" in msg or "invalidparameter" in msg))

    def chat_with_image(self, text_prompt: str, image_base64: str,
                        image_detail: str = "high",
                        system_prompt: str = "",
                        temperature: float = 0.3) -> Dict[str, Any]:
        """发送带图片的对话请求（VLM）

        Args:
            text_prompt: 文本提示
            image_base64: base64 编码的图片数据（不含 data:image/... 前缀）
            image_detail: 图片精度 "low" / "high" / "auto"
            system_prompt: 系统提示词
            temperature: 温度参数

        Returns:
            {"content": str, "model": str, "usage": dict, "raw": dict}
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": text_prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_base64}",
                        "detail": image_detail,
                    },
                },
            ],
        })

        return self.chat(messages, temperature=temperature)

    def _post(self, path: str, payload: dict) -> dict:
        """发送 POST 请求"""
        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        try:
            resp = requests.post(
                url, json=payload, headers=headers,
                timeout=self.timeout_ms / 1000,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            raise LLMClientError(f"API 返回错误: {resp.status_code} {resp.text[:500]}") from e
        except requests.exceptions.ConnectionError as e:
            raise LLMClientError(f"无法连接到 API: {url}") from e
        except requests.exceptions.Timeout as e:
            raise LLMClientError(f"API 请求超时 ({self.timeout_ms}ms)") from e
        except Exception as e:
            raise LLMClientError(f"API 请求失败: {e}") from e
