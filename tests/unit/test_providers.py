"""Mock HTTP provider integration tests (no claim of live provider verification)."""

import json

import httpx
import pytest

from agentic_rag.models.tool import ToolSpec
from agentic_rag.providers.open_embed import OpenAIEmbed
from agentic_rag.providers.openai import OpenAIChat


async def test_openai_compatible_tool_call_parsed_as_action() -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["tools"][0]["function"]["name"] == "search"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "search",
                                        "arguments": '{"query":"Saturn rings"}',
                                    }
                                }
                            ]
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        provider = OpenAIChat("mock-chat", "dummy", client=client)
        tools = [
            ToolSpec(
                "search",
                "Read search",
                {"type": "object", "properties": {"query": {"type": "string"}}},
            )
        ]
        actions = await provider.choose_tools("Saturn", tools, [])
        assert [(item.tool, item.arguments) for item in actions] == [
            ("search", {"query": "Saturn rings"})
        ]
        assert len(requests) == 1
    finally:
        await client.aclose()


async def test_route_classification_requests_a_json_object():
    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"mode":"direct","reason":"General concept"}'}}
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = OpenAIChat("mock-chat", "dummy", client=client)
        result = await provider.classify("Explain decorators", True, [])
        assert result["mode"] == "direct"


async def test_openai_compatible_rejects_unregistered_function() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [{"function": {"name": "erase_all", "arguments": "{}"}}]
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    try:
        provider = OpenAIChat("mock", "dummy", client=client)
        with pytest.raises(ValueError, match="unavailable"):
            await provider.choose_tools(
                "bad", [ToolSpec("search", "", {"type": "object", "properties": {}})], []
            )
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    "url", ["http://untrusted.invalid", "file:///etc/passwd", "https://user:pass@private.invalid"]
)
def test_openai_model_url_must_not_be_unsafe(url) -> None:
    with pytest.raises(ValueError, match="HTTPS or loopback"):
        OpenAIChat("mock", "fake", base_url=url)


async def test_embedding_mock_validates_batch_dimensions() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "data": [
                        {"index": 0, "embedding": [0.1, 0.2]},
                        {"index": 1, "embedding": [0.3, 0.4]},
                    ]
                },
            )
        )
    )
    try:
        embed = OpenAIEmbed("mock-embedding", "dummy", client=client)
        assert await embed.documents(["first", "second"]) == [[0.1, 0.2], [0.3, 0.4]]
    finally:
        await client.aclose()


async def test_embedding_mock_rejects_dimension_mismatch() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "data": [
                        {"index": 0, "embedding": [0.1]},
                        {"index": 1, "embedding": [0.3, 0.4]},
                    ]
                },
            )
        )
    )
    try:
        embed = OpenAIEmbed("mock-embedding", "dummy", client=client)
        with pytest.raises(ValueError, match="dimensions"):
            await embed.documents(["one", "two"])
    finally:
        await client.aclose()


@pytest.mark.parametrize("url", ["http://localhost:20128/v1", "http://127.0.0.1:20128/v1"])
async def test_embedding_allows_local_http_gateway(url) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"{url}/embeddings"
        assert request.headers["authorization"] == "Bearer embedding-test-key"
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        embed = OpenAIEmbed("embed-test", "embedding-test-key", base_url=url, client=client)
        assert await embed.query("refunds") == [0.1, 0.2]


@pytest.mark.parametrize(
    "url",
    [
        "http://untrusted.invalid",
        "http://localhost.evil.invalid",
        "file:///etc/passwd",
        "http://user:pass@localhost:20128/v1",
        "https://user:pass@private.invalid",
    ],
)
def test_embedding_rejects_unsafe_endpoint(url) -> None:
    with pytest.raises(ValueError, match="HTTPS or loopback"):
        OpenAIEmbed("mock", "dummy", base_url=url)


async def test_parallel_document_calls_accumulate_usage_without_cross_run_leakage():
    import asyncio

    def respond(request):
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Answer"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = OpenAIChat("mock", "dummy", client=client)

        async def run(calls):
            provider.reset_usage()
            await asyncio.gather(
                *(provider.complete([{"role": "user", "content": "Hello"}]) for _ in range(calls))
            )
            return provider.usage()

        first, second = await asyncio.gather(run(2), run(3))
        assert first["total_tokens"] == 6
        assert second["total_tokens"] == 9
