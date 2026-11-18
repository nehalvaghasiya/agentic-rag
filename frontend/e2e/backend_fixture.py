"""Browser-only fixture of the current backend, with scripted model providers."""

import asyncio
import json
import os

from agentic_rag.api.app import create_app as application
from agentic_rag.api.deps import get_principal
from agentic_rag.core.config import Settings
from agentic_rag.models.principal import Principal
from agentic_rag.providers.fake import FakeChat
from agentic_rag.models.grounded import GroundedAnswer


class BrowserChat(FakeChat):
    async def answer_document(self, messages, evidence, *, instruction=""):
        if 'top 5 takeaways' in messages[-1]['content'].lower() and len(evidence) >= 5:
            return GroundedAnswer('\n\n'.join(
                f'{i}. {source.text[:150]} [source:{source.chunk_id}]'
                for i, source in enumerate(evidence[:5], 1)
            ), True)
        return await super().answer_document(messages, evidence, instruction=instruction)

    async def stream(self, messages):
        question = messages[-1]['content']
        if question == 'Explain answer versions':
            self.version_count = getattr(self, 'version_count', 0) + 1
            yield f'Answer version {self.version_count}.'
            return
        if question == 'Explain regeneration recovery':
            self.recovery_count = getattr(self, 'recovery_count', 0) + 1
            if self.recovery_count == 2:
                raise RuntimeError('private-provider-sentinel')
            if self.recovery_count > 2:
                for _ in range(60):
                    await asyncio.sleep(.05)
                    yield 'Replacement in progress. '
            else:
                yield 'The original answer is available.'
            return
        if 'controlled failure' in question:
            raise RuntimeError('private-provider-sentinel')
        if 'respond slowly' in question:
            for _ in range(60):
                await asyncio.sleep(.05)
                yield 'Working on the requested response. '
        else:
            async for token in super().stream(messages):
                yield token


def create_app():
    url = os.environ.get('AGENTIC_RAG_TEST_DATABASE_URL')
    tenant = os.environ.get('TEST_TENANT_ID', 'browser-test-tenant')
    app = application(Settings(environment='demo', store='postgres' if url else 'fake', provider='fake',
        embedding_provider='fake', database_url=url or None, worker_tenant_id=tenant,
        allow_origins=json.loads(os.environ.get('CORS_ORIGINS', '[]'))))
    async def identity():
        return Principal('browser-user', tenant, frozenset({'admin','analyst'}))
    app.dependency_overrides[get_principal] = identity
    # Replace the provider inside lifespan; all requests still use the public service.
    original = app.router.lifespan_context
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            runtime = application.state.runtime
            scripted = BrowserChat()
            runtime.chat = runtime.agent.chat = runtime.sessions.chat = scripted
            yield
    app.router.lifespan_context = lifespan
    return app
