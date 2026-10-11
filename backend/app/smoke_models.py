"""Manual real-model check: `python -m app.smoke_models` (from backend/, MODEL_MODE=real in backend/.env).

Sends one short prompt to the small and large models, then one agent turn with tools,
and prints provider, model, latency, and token usage. Never prints keys.
"""

import sys
import tempfile
import time
from pathlib import Path

from . import db
from .agent import AgentContext, AgentFailed, ModelAgent
from .catalog import get_scenario
from .config import get_settings
from .models import ModelError, build_clients


def main() -> int:
    settings = get_settings()
    if settings.model_mode != "real":
        print("MODEL_MODE is 'mock'. Set MODEL_MODE=real (and the model settings) in backend/.env first.")
        return 2
    clients = build_clients(settings)
    failed = False
    for size, client in clients.items():
        started = time.monotonic()
        try:
            reply = client.chat([{"role": "user", "content": "Reply with the single word OK."}])
            print(f"{size}: {client.provider}:{client.model} ok in {time.monotonic() - started:.1f}s, "
                  f"tokens {reply.prompt_tokens}/{reply.completion_tokens}: {(reply.content or '').strip()[:60]!r}")
        except ModelError as error:
            failed = True
            print(f"{size}: {client.provider}:{client.model} FAILED: {error}")
    if failed:
        return 1
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "smoke.sqlite3"
        db.init_db(path)
        connection = db.connect(path)
        try:
            context = AgentContext(get_scenario(connection, "practice"), "Venue",
                                   {"venue": None, "catering": None, "supplies": []}, [],
                                   "Which venue meets all the requirements?")
            reply = ModelAgent(clients, settings.agent_max_steps).reply("small", context, connection)
            tools = [name for call in reply.calls for name in call.tools]
            print(f"agent (small): {len(reply.calls)} calls, tools {tools}\n  reply: {reply.text}")
        except AgentFailed as failure:
            print(f"agent (small) FAILED: {failure.calls[-1].error}")
            return 1
        finally:
            connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
