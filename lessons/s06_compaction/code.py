"""Stage 6: original offline teaching snapshot; not the dsh runtime."""

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
        """A projection, not mutation of the durable source events."""
        surface = []
        for event in self._events:
            kind, data = (event['type'], event['data'])
            if kind in {'user/message', 'assistant/message', 'tool/result'}:
                surface.append(event)
            elif kind == 'surface/replace':
                removed = set(data['seqs'])
                indexes = [i for i, item in enumerate(surface) if item['seq'] in removed]
                if not indexes:
                    raise ValueError('replacement no longer belongs to surface')
                first = indexes[0]
                surface = [item for item in surface if item['seq'] not in removed]
                surface.insert(first, {'seq': event['seq'], 'type': 'user/message', 'data': {'text': data['summary'], 'summary': True}})
        return snapshot(surface)

    def messages(self):
        return [{'role': {'user/message': 'user', 'assistant/message': 'assistant', 'tool/result': 'tool'}[event['type']], **event['data']} for event in self.surface()]

    def compact_prefix(self, count, summary):
        visible = self.surface()
        if type(count) is not int or not 0 < count <= len(visible):
            raise ValueError('invalid visible prefix')
        selected = visible[:count]
        if pending_calls(selected):
            raise ValueError('compaction would cut a tool call/result pair')
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError('summary must be nonempty')
        return self.append('surface/replace', seqs=[e['seq'] for e in selected], summary=summary)

def pending_calls(events):
    pending = set()
    seen = set()
    for event in events:
        if event["type"] == "assistant/message":
            for call in event["data"].get("calls", []):
                if call["id"] in seen:
                    raise ValueError("duplicate tool call id")
                seen.add(call["id"])
                pending.add(call["id"])
        elif event["type"] == "tool/result":
            call_id = event["data"]["call_id"]
            if call_id not in pending:
                raise ValueError("orphan or duplicate result")
            pending.remove(call_id)
    return pending

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

@dataclass
class Policy:
    decide: Callable[[dict], str] = lambda _: "allow"
    approve: Callable[[dict], bool] | None = None
    guards: tuple[Callable[[dict], str | None], ...] = ()

    def check(self, call):
        decision = self.decide(snapshot(call))
        if decision == "ask":
            decision = "allow" if self.approve and self.approve(snapshot(call)) is True else "deny"
        if decision != "allow":
            return "DENIED"
        # Guards are monotonic: none can turn a prior denial into an allowance.
        for guard in self.guards:
            reason = guard(snapshot(call))
            if reason is not None:
                return "GUARD_DENIED"
        return None

def parallel_safe(tool, args):
    try:
        return tool is not None and tool.validate(args) is True and tool.parallel(args) is True
    except Exception:
        return False

def recover_missing(session):
    """Record conservative facts; never retry tools."""
    pending = pending_calls(session.surface())
    started = {e["data"]["call_id"] for e in session.events if e["type"] == "tool/call"}
    result = {}
    for call_id in sorted(pending):
        code = "TOOL_OUTCOME_UNKNOWN" if call_id in started else "TOOL_NOT_STARTED"
        session.append("tool/result", call_id=call_id, ok=False, code=code)
        result[call_id] = code
    return result

async def run_batch(calls, registry, scope, session, policy=None, token=None, limit=2):
    """Bounded waves + exclusive barriers. Not upstream's rolling-pool scheduler."""
    if type(limit) is not int or limit < 1:
        raise ValueError("limit must be a positive integer")
    calls = snapshot(calls)
    if len({c["id"] for c in calls}) != len(calls):
        raise ValueError("duplicate call ids")
    policy, token = policy or Policy(), token or CancelToken()
    results, cursor = [], 0

    async def invoke(call, tool):
        session.append("tool/call", call_id=call["id"], name=call["name"])
        if token.cancelled:
            return {"ok": False, "code": "ABORTED_BEFORE_DISPATCH"}
        try:
            denied = policy.check(call)
            if denied:
                return {"ok": False, "code": denied}
            if tool is None:
                return {"ok": False, "code": "UNKNOWN_TOOL"}
            if tool.validate(call["args"]) is not True:
                return {"ok": False, "code": "INVALID_ARGUMENTS"}
        except Exception:
            return {"ok": False, "code": "POLICY_ERROR"}
        if token.cancelled:
            return {"ok": False, "code": "ABORTED_BEFORE_DISPATCH"}
        try:
            value = snapshot(await tool.body(snapshot(call["args"]), token))
            return {"ok": False, "code": "ABORTED"} if token.cancelled else {"ok": True, "value": value}
        except Exception as exc:
            return {"ok": False, "code": "TOOL_ERROR", "error": type(exc).__name__}

    while cursor < len(calls):
        group = [calls[cursor]]
        first = registry.get(group[0]["name"], scope)
        if parallel_safe(first, group[0]["args"]):
            for call in calls[cursor + 1:cursor + limit]:
                if not parallel_safe(registry.get(call["name"], scope), call["args"]):
                    break
                group.append(call)
        # Preserve order; cooperative cancellation and caught errors leave each body awaited.
        outcomes = await asyncio.gather(*(invoke(c, registry.get(c["name"], scope)) for c in group))
        for call, outcome in zip(group, outcomes):
            session.append("tool/result", call_id=call["id"], **outcome)
            results.append({"call_id": call["id"], **outcome})
        cursor += len(group)
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
    before = len(session.events)
    session.compact_prefix(3, 'Confirmed: double 21 is 42.')
    return {'log_before': before, 'log_after': len(session.events), 'surface_count': len(session.messages())}


if __name__ == '__main__':
    print(json.dumps(asyncio.run(demo()), ensure_ascii=False, indent=2))
