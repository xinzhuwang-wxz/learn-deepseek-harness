"""Stage 3: original offline teaching snapshot; not the dsh runtime."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from typing import Any, Awaitable, Callable


def snapshot(value: Any) -> Any:
    """Create a JSON-normalized copy; reject non-finite or unsupported values."""
    return json.loads(json.dumps(value, allow_nan=False))

class ScriptedModel:
    """Record each actual request, then return a predetermined response."""
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def respond(self, messages):
        self.requests.append(snapshot(messages))
        try:
            return snapshot(next(self.responses))
        except StopIteration as exc:
            raise RuntimeError("script ended without a final response") from exc

class Session:

    def __init__(self, events=None):
        self._events = snapshot(events or [])
        if any((event['seq'] != i for i, event in enumerate(self._events))):
            raise ValueError('event sequence must be contiguous from zero')

    @property
    def events(self):
        return snapshot(self._events)

    def append(self, kind, **data):
        event = snapshot({'seq': len(self._events), 'type': kind, 'data': data})
        self._events.append(event)
        return event['seq']

    def surface(self):
        return snapshot([e for e in self._events if e['type'] in {'user/message', 'assistant/message', 'tool/result'}])

    def messages(self):
        return [{'role': {'user/message': 'user', 'assistant/message': 'assistant', 'tool/result': 'tool'}[event['type']], **event['data']} for event in self.surface()]

@dataclass(eq=False)
class Scope:
    parent: Scope | None = None
    disposers: list[Callable] = field(default_factory=list)
    closed: bool = False

    def owns(self, dispose):
        if self.closed:
            raise RuntimeError("scope already disposed")
        self.disposers.append(dispose)

    def close(self):
        if self.closed:
            return
        self.closed = True
        # Resource-specific async teardown is deliberately outside this lesson.
        for dispose in reversed(self.disposers):
            dispose()
        self.disposers.clear()

    def ancestors(self):
        cursor = self
        while cursor is not None:
            yield cursor
            cursor = cursor.parent

@dataclass
class Tool:
    name: str
    body: Callable[[dict, 'CancelToken'], Awaitable[Any]]
    validate: Callable[[dict], bool] = lambda _: True
    parallel: Callable[[dict], bool] = lambda _: False

class Registry:
    def __init__(self):
        self.entries = []

    def register(self, scope, tool):
        token = object()
        entry = (token, scope, tool)
        scope.owns(lambda: self._remove(token))
        self.entries.append(entry)
        return lambda: self._remove(token)

    def _remove(self, token):
        self.entries[:] = [e for e in self.entries if e[0] is not token]

    def get(self, name, scope):
        for layer in scope.ancestors():
            for _, owner, tool in reversed(self.entries):
                if owner is layer and tool.name == name:
                    return tool
        return None

@dataclass
class CancelToken:
    cancelled: bool = False

async def run_batch(calls, registry, scope, session, policy=None, token=None, limit=1):
    results = []
    for call in calls:
        tool = registry.get(call['name'], scope)
        session.append('tool/call', call_id=call['id'], name=call['name'])
        try:
            if tool is None: raise ValueError('unknown tool')
            value = await tool.body(call['args'], CancelToken())
            outcome = {'ok': True, 'value': value}
        except Exception as exc:
            outcome = {'ok': False, 'error': type(exc).__name__}
        session.append('tool/result', call_id=call['id'], **outcome)
        results.append(outcome)
    return results


async def agent_loop(script, registry, scope, session, max_steps=4, policy=None):
    """The fake provider receives the derived history on every actual request."""
    model = script if isinstance(script, ScriptedModel) else ScriptedModel(script)
    for step in range(max_steps):
        session.append("step/start", step=step)
        response = model.respond(session.messages())
        session.append("assistant/message", **response)
        calls = response.get("calls", [])
        if calls:
            await run_batch(calls, registry, scope, session, policy)
        session.append("step/end", step=step)
        if not calls:
            return session.messages()
    raise RuntimeError("teaching step budget exhausted")

async def demo():
    session = Session()
    session.append('user/message', text='Double 21')
    root, registry = Scope(), Registry()
    async def double(args, token): return args['value'] * 2
    registry.register(root, Tool('double', double, validate=lambda a: type(a.get('value')) is int,
                                  parallel=lambda _: True))
    calls = [{'id': 'c1', 'name': 'double', 'args': {'value': 21}}]
    await agent_loop([{'calls': calls}, {'text': '42'}], registry, root, session)
    visible_before = registry.get('double', root) is not None
    root.close()
    return {'visible_before': visible_before, 'removed_after_dispose': registry.get('double', root) is None}


if __name__ == '__main__':
    print(json.dumps(asyncio.run(demo()), ensure_ascii=False, indent=2))
