"""Stage 2: original offline teaching snapshot; not the dsh runtime."""

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

def run(script, session, max_steps=4):
    tools = {'double': lambda args: args['value'] * 2}
    model = ScriptedModel(script)
    for step in range(max_steps):
        session.append('step/start', step=step)
        response = model.respond(session.messages())
        session.append('assistant/message', **response)
        calls = response.get('calls', [])
        for call in calls:
            session.append('tool/call', call_id=call['id'], name=call['name'])
            try:
                outcome = {'ok': True, 'value': tools[call['name']](call['args'])}
            except (KeyError, TypeError, ValueError) as exc:
                outcome = {'ok': False, 'error': type(exc).__name__}
            session.append('tool/result', call_id=call['id'], **outcome)
        session.append('step/end', step=step)
        if not calls: return session.messages()
    raise RuntimeError('script ended without final response')


async def demo():
    session = Session()
    session.append('user/message', text='Double 21')
    run([{'calls': [{'id': 'c1', 'name': 'double', 'args': {'value': 21}}]}, {'text': '42'}], session)
    return {'event_types': [e['type'] for e in session.events], 'model_messages': session.messages()}


if __name__ == '__main__':
    print(json.dumps(asyncio.run(demo()), ensure_ascii=False, indent=2))
