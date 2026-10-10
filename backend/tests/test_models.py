import pytest

from app.config import Settings
from app.models import ChatClient, ModelError, build_clients
from tests.fakes import FakeOpenAIServer, completion


@pytest.fixture
def fake_server():
    servers = []

    def make(responses):
        server = FakeOpenAIServer(responses)
        servers.append(server)
        return server
    yield make
    for server in servers:
        server.close()


def test_openai_request_and_tool_call_parsing(fake_server):
    server = fake_server([(200, completion(tool_calls=[("search_catalog", {"query": "hall"})]))])
    client = ChatClient("large", "openai", "gpt-test", server.url, "sk-test-not-real", 5)
    reply = client.chat([{"role": "user", "content": "hi"}], [{"type": "function", "function": {"name": "x"}}])
    request = server.requests[0]
    assert request["path"] == "/v1/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer sk-test-not-real"
    assert request["body"]["model"] == "gpt-test" and request["body"]["tools"]
    assert request["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert reply.tool_calls[0].name == "search_catalog" and reply.tool_calls[0].arguments == '{"query": "hall"}'
    assert (reply.prompt_tokens, reply.completion_tokens) == (12, 4)


def test_plain_answer_without_tools_or_key(fake_server):
    server = fake_server([(200, completion(content="Pick Meadow Hall."))])
    reply = ChatClient("small", "ollama", "mixtral:8x7b", server.url, None, 5).chat([{"role": "user", "content": "?"}])
    assert reply.content == "Pick Meadow Hall." and reply.tool_calls == []
    assert "Authorization" not in server.requests[0]["headers"]
    assert "tools" not in server.requests[0]["body"]


@pytest.mark.parametrize("response, expected", [
    ((401, {"error": {"message": "Incorrect API key provided: sk-test-not-real"}}), "HTTP 401"),
    ((500, "oops"), "HTTP 500"),
    ((200, "not json"), "invalid JSON"),
    ((200, {"choices": []}), "unexpected response"),
])
def test_provider_failures_become_safe_model_errors(fake_server, response, expected):
    server = fake_server([response])
    with pytest.raises(ModelError, match=expected) as raised:
        ChatClient("large", "openai", "gpt-test", server.url, "sk-test-not-real", 5).chat([])
    assert "sk-test-not-real" not in str(raised.value)


def test_timeouts_and_unreachable_servers(fake_server):
    server = fake_server([("hang", 2)])
    with pytest.raises(ModelError, match="unreachable"):
        ChatClient("small", "ollama", "m", server.url, None, 0.3).chat([])
    with pytest.raises(ModelError, match="unreachable"):
        ChatClient("small", "ollama", "m", "http://127.0.0.1:9/v1", None, 1).chat([])


def test_build_clients_routes_providers():
    settings = Settings(_env_file=None, model_mode="real", small_model="ollama:mixtral:8x7b",
                        large_model="openai:gpt-4-turbo", openai_api_key="sk-test-not-real",
                        ollama_base_url="http://ollama.test:11434/")
    clients = build_clients(settings)
    assert (clients["small"].provider, clients["small"].model) == ("ollama", "mixtral:8x7b")
    assert clients["small"]._url == "http://ollama.test:11434/v1/chat/completions"
    assert clients["small"]._api_key is None
    assert (clients["large"].provider, clients["large"].model) == ("openai", "gpt-4-turbo")
    assert clients["large"]._url == "https://api.openai.com/v1/chat/completions"
