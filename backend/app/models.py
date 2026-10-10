"""Small/large model clients (#35). OpenAI and Ollama both speak the OpenAI chat API,
so one stdlib HTTP client covers both; keys are sent only to OpenAI and never logged."""

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from .config import Settings, parse_model_spec


class ModelError(Exception):
    """A provider call failed. The message is safe to log: no keys or response bodies."""


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass
class ModelReply:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class ChatClient:
    def __init__(self, size: str, provider: str, model: str, base_url: str,
                 api_key: str | None, timeout: float):
        self.size, self.provider, self.model = size, provider, model
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._timeout = timeout

    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ModelReply:
        payload: dict = {"model": self.model, "messages": messages, "temperature": 0}
        if tools:
            payload["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(self._url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise ModelError(f"{self.provider} returned HTTP {error.code}") from None
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as error:
            raise ModelError(f"{self.provider} unreachable ({type(error).__name__})") from None
        except json.JSONDecodeError:
            raise ModelError(f"{self.provider} returned invalid JSON") from None
        try:
            message = data["choices"][0]["message"]
            calls = [ToolCall(call["id"], call["function"]["name"], call["function"].get("arguments") or "{}")
                     for call in message.get("tool_calls") or []]
        except (KeyError, IndexError, TypeError):
            raise ModelError(f"{self.provider} returned an unexpected response") from None
        usage = data.get("usage") or {}
        return ModelReply(message.get("content"), calls, usage.get("prompt_tokens"), usage.get("completion_tokens"))


def build_clients(settings: Settings) -> dict[str, ChatClient]:
    clients = {}
    for size, spec in (("small", settings.small_model), ("large", settings.large_model)):
        provider, model = parse_model_spec(spec)
        if provider == "openai":
            key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
            clients[size] = ChatClient(size, provider, model, settings.openai_base_url, key, settings.model_timeout_seconds)
        else:
            clients[size] = ChatClient(size, provider, model, f"{settings.ollama_base_url.rstrip('/')}/v1",
                                       None, settings.model_timeout_seconds)
    return clients

