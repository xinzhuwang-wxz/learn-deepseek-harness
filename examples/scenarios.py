"""Observable probes for the final teaching runtime."""
import asyncio
from .harness import *

async def double(args, token):
    return args['value'] * 2


def call(identifier='c1', name='double', **args):
    return {'id': identifier, 'name': name, 'args': args or {'value': 21}}

async def capstone():
    scope, registry, session = Scope(), Registry(), Session()
    registry.register(scope, Tool('double', double, validate=lambda a: type(a.get('value')) is int,
                                  parallel=lambda _: True))
    session.append('user/message', text='Double 21')
    script = [{'calls': [call()]}, {'text': 'The result is 42.'}]
    model = ScriptedModel(script)
    await agent_loop(model, registry, scope, session)
    observed = model.requests[1][-1]['value']
    before = len(session.events)
    session.compact_prefix(3, 'User asked to double 21; result 42 was confirmed.')
    child = session.fork(len(session.events) - 1)
    child.append('user/message', text='Explain the result to a new reader')
    scope.close()
    return {'value': observed, 'durable_events_before_compaction': before,
            'durable_events_after_compaction': len(session.events),
            'visible_messages': len(session.messages()), 'child_depth': child.depth,
            'parent_unchanged_after_child_write': len(session.events) + 1 == len(child.events),
            'tool_removed_after_dispose': registry.get('double', scope) is None}

if __name__ == '__main__':
    print(json.dumps(asyncio.run(capstone()), ensure_ascii=False, indent=2))
