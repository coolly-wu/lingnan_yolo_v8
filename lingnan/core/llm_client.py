"""双模式大语言模型客户端（本地 / 云端，均 OpenAI 兼容）

依据技术规范 §8.16.3.3：
  - 本地模式：OpenAI 兼容 HTTP 服务（Ollama / llama.cpp server / LM Studio）
  - 云端模式（可选、非默认）：DeepSeek / 豆包 / 通义等 OpenAI 兼容 API

两种模式共用同一套 requests 调用，仅 base_url / api_key / model 不同。
`import requests` 延迟到 chat() 内，任何失败（缺库 / 超时 / 连接拒绝 / 非 200 /
返回结构异常）都抛 LLMError，由上层捕获并降级为模板填充（FR-G7）。
"""

from __future__ import annotations

from dataclasses import dataclass


class LLMError(Exception):
    """LLM 调用失败（统一异常，消息为中文友好提示）。"""


@dataclass
class LLMConfig:
    mode: str = "local"            # "local" | "cloud"
    base_url: str = "http://localhost:11434/v1"
    api_key: str = ""
    model: str = ""
    timeout: float = 60.0
    temperature: float = 0.4

    @classmethod
    def from_settings(cls, s) -> "LLMConfig":
        return cls(
            mode=getattr(s, "llm_mode", "local"),
            base_url=getattr(s, "llm_base_url", "") or "",
            api_key=getattr(s, "llm_api_key", "") or "",
            model=getattr(s, "llm_model", "") or "",
        )


class LLMClient:
    """OpenAI 兼容 /chat/completions 客户端。"""

    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def is_configured(self) -> bool:
        """是否具备发起调用的最小配置（base_url + model 必填）。"""
        return bool(self.cfg.base_url.strip() and self.cfg.model.strip())

    def _endpoint(self) -> str:
        base = self.cfg.base_url.strip().rstrip("/")
        # 允许用户填到 /v1 或根；统一拼到 /chat/completions
        if base.endswith("/chat/completions"):
            return base
        return base + "/chat/completions"

    def chat(self, system: str, user: str) -> str:
        if not self.is_configured():
            raise LLMError("尚未配置大模型服务地址或模型名称，请在【设置】中填写。")
        try:
            import requests  # 延迟导入
        except Exception as e:  # pragma: no cover - 环境缺库
            raise LLMError(f"未安装 requests 库，无法调用大模型：{e!r}") from e

        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        payload = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.cfg.temperature,
            "stream": False,
        }
        try:
            resp = requests.post(
                self._endpoint(), json=payload, headers=headers,
                timeout=self.cfg.timeout,
            )
        except Exception as e:
            raise LLMError(
                f"无法连接大模型服务（{self.cfg.base_url}）：{e!r}"
            ) from e
        if resp.status_code != 200:
            raise LLMError(
                f"大模型服务返回错误 {resp.status_code}：{resp.text[:200]}"
            )
        try:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMError(f"大模型返回结构异常，无法解析：{e!r}") from e
        if not content or not content.strip():
            raise LLMError("大模型返回了空内容。")
        return content
