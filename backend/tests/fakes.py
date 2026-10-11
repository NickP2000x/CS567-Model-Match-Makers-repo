"""Test doubles for model calls: a scripted in-process client and a fake OpenAI-compatible server."""

import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.models import ModelReply, ToolCall


def answer(text: str, prompt: int = 10, completion: int = 5) -> ModelReply:
    return ModelReply(text, [], prompt, completion)


def tool(name: str, arguments: dict | str, call_id: str = "call-1") -> ModelReply:
    args = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return ModelReply(None, [ToolCall(call_id, name, args)], 20, 3)


class ScriptedClient:
    """Returns queued replies; an item may be an Exception to raise or a callable(messages)."""

    def __init__(self, size: str, replies: list, provider: str = "openai", model: str | None = None):
        self.size, self.provider, self.model = size, provider, model or f"fake-{size}"
        self.replies = list(replies)
        self.requests: list[tuple[list[dict], list | None]] = []

    def chat(self, messages, tools=None):
        self.requests.append((copy.deepcopy(messages), tools))
        if not self.replies:
            raise AssertionError("ScriptedClient ran out of replies")
        item = self.replies.pop(0)
        if callable(item):
            item = item(messages)
        if isinstance(item, Exception):
            raise item
        return item


class FakeOpenAIServer:
    """A local OpenAI-compatible /chat/completions endpoint with scripted JSON responses."""

    def __init__(self, responses: list):
        self.responses = list(responses)  # each: (status, body dict or raw str) or "hang"
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                outer.requests.append({"path": self.path, "headers": dict(self.headers),
                                       "body": json.loads(self.rfile.read(length))})
                status, body = outer.responses.pop(0)
                if status == "hang":
                    threading.Event().wait(body)
                    return
                data = body if isinstance(body, str) else json.dumps(body)
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(data.encode())

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def completion(content=None, tool_calls=None, prompt=12, completion_tokens=4) -> dict:
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = [{"id": f"call-{i}", "type": "function",
                                  "function": {"name": name, "arguments": json.dumps(args)}}
                                 for i, (name, args) in enumerate(tool_calls)]
    return {"choices": [{"message": message}],
            "usage": {"prompt_tokens": prompt, "completion_tokens": completion_tokens}}
