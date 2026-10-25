"""Observe S03 ownership, lookup, identity-based disposal, and execution."""
import argparse
import asyncio
import json
from load_lesson import load

h = load('s03_plugins')


def tool(label, factor):
    async def body(args, token):
        return {'provider': label, 'value': args['value'] * factor}
    return h.Tool('double', body)


def provider(registry, scope, labels):
    found = registry.get('double', scope)
    return next((name for name, item in labels.items() if found is item), None)


def ownership_case():
    root = h.Scope()
    child_a, child_b = h.Scope(root), h.Scope(root)
    registry = h.Registry()
    labels = {'root': tool('root', 2), 'a': tool('a', 3)}
    registry.register(root, labels['root'])
    registry.register(child_a, labels['a'])
    scopes = {'root': root, 'child_a': child_a, 'child_b': child_b}
    before = {name: provider(registry, scope, labels) for name, scope in scopes.items()}
    child_a.close()
    after = {name: provider(registry, scope, labels) for name, scope in scopes.items()}
    assert before == {'root': 'root', 'child_a': 'a', 'child_b': 'root'}
    assert after == {'root': 'root', 'child_a': 'root', 'child_b': 'root'}
    return {'before_close': before, 'after_child_a_close': after,
            'child_a_closed': child_a.closed, 'remaining_entries': len(registry.entries)}


def stale_case():
    scope, registry = h.Scope(), h.Registry()
    labels = {'old': tool('old', 2), 'new': tool('new', 3)}
    dispose_old = registry.register(scope, labels['old'])
    dispose_new = registry.register(scope, labels['new'])
    before = provider(registry, scope, labels)
    dispose_old()
    after_once = provider(registry, scope, labels)
    dispose_old()
    after_twice = provider(registry, scope, labels)
    remaining = len(registry.entries)
    naive = {'double': labels['old']}
    naive['double'] = labels['new']
    naive.pop('double', None)
    dispose_new()
    assert [before, after_once, after_twice] == ['new', 'new', 'new']
    assert remaining == 1 and registry.get('double', scope) is None
    return {'before': before, 'after_old_once': after_once, 'after_old_twice': after_twice,
            'remaining_before_new_dispose': remaining,
            'after_new_dispose': provider(registry, scope, labels),
            'naive_name_delete_lost_new': 'double' not in naive}


def lifecycle_case():
    scope, order = h.Scope(), []
    scope.owns(lambda: order.append('connection'))
    scope.owns(lambda: order.append('subscription'))
    scope.close()
    scope.close()
    registry = h.Registry()
    try:
        registry.register(scope, tool('late', 2))
    except RuntimeError as exc:
        error = str(exc)
    else:
        raise AssertionError('closed scope accepted a registration')
    assert order == ['subscription', 'connection'] and not registry.entries
    return {'cleanup_order': order, 'disposers_after_close': len(scope.disposers),
            'late_registration_error': error, 'entries_after_rejection': len(registry.entries)}


def noncascade_case():
    root, registry = h.Scope(), h.Registry()
    child = h.Scope(root)
    labels = {'root': tool('root', 2), 'child': tool('child', 3)}
    registry.register(root, labels['root'])
    registry.register(child, labels['child'])
    root.close()
    result = {'root_closed': root.closed, 'child_closed': child.closed,
              'child_provider': provider(registry, child, labels),
              'remaining_entries': len(registry.entries)}
    assert result == {'root_closed': True, 'child_closed': False,
                      'child_provider': 'child', 'remaining_entries': 1}
    child.close()
    return result


async def execution_case():
    root, registry, session = h.Scope(), h.Registry(), h.Session()
    child = h.Scope(root)
    registry.register(root, tool('root', 2))
    registry.register(child, tool('child', 3))
    session.append('user/message', text='Double 21')
    model = h.ScriptedModel([
        {'calls': [{'id': 'c1', 'name': 'double', 'args': {'value': 21}}]},
        {'text': 'done'},
    ])
    await h.agent_loop(model, registry, child, session)
    actual = model.requests[1][-1]
    assert actual['value'] == {'provider': 'child', 'value': 63}
    assert actual['call_id'] == 'c1'
    return {'second_request_last_message': actual,
            'event_types': [e['type'] for e in session.events],
            'requests': len(model.requests)}


async def unchecked_case():
    root, registry, session, entered = h.Scope(), h.Registry(), h.Session(), []
    async def body(args, token):
        entered.append(args['value'])
        return args['value'] * 2
    definition = h.Tool('double', body, validate=lambda _: False)
    registry.register(root, definition)
    calls = [{'id': 'c1', 'name': 'double', 'args': {'value': 21}}]
    session.append('assistant/message', calls=calls)
    outcomes = await h.run_batch(calls, registry, root, session)
    assert entered == [21] and outcomes[0]['value'] == 42
    return {'validator_would_return': definition.validate(calls[0]['args']),
            'body_inputs': entered, 'outcomes': outcomes}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=['ownership', 'stale', 'lifecycle', 'noncascade', 'execution', 'unchecked', 'all'], nargs='?', default='all')
    args = parser.parse_args()
    sync = {'ownership': ownership_case, 'stale': stale_case,
            'lifecycle': lifecycle_case, 'noncascade': noncascade_case}
    asynchronous = {'execution': execution_case, 'unchecked': unchecked_case}
    if args.case == 'all':
        result = {name: fn() for name, fn in sync.items()}
        for name, fn in asynchronous.items():
            result[name] = await fn()
    elif args.case in sync:
        result = sync[args.case]()
    else:
        result = await asynchronous[args.case]()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        asyncio.run(asyncio.wait_for(main(), timeout=3))
    except TimeoutError:
        raise SystemExit('Walkthrough exceeded 3 seconds. Check whether an edited tool waits for work that cannot start; no network or model service is involved.')
