"""Deterministic, in-memory experiments for ordered batch settlement."""
import argparse
import asyncio
import json
from load_lesson import load

h = load('s05_settlement')


def call(ident, name='read'):
    return {'id': ident, 'name': name, 'args': {'id': ident}}


async def batch_case(limit=2, force_inversion=False, unsafe_exclusive=False):
    if force_inversion and limit < 2:
        raise ValueError('the inverse-completion experiment needs two runnable calls')
    scope, registry, session = h.Scope(), h.Registry(), h.Session()
    document, active = {'version': 0}, set()
    peak, events, completed, overlaps = 0, [], [], []
    b_done = asyncio.Event()

    async def body(args, token):
        nonlocal peak
        ident = args['id']
        active.add(ident)
        peak = max(peak, len(active))
        events.append('start:' + ident)
        if 'write' in active and len(active) > 1:
            overlaps.append(sorted(active))
        seen_version = document['version']
        if ident == 'a' and force_inversion:
            await b_done.wait()
        await asyncio.sleep(0)  # Yield once; no elapsed-time assumption.
        if ident == 'write':
            document['version'] = 1
            seen_version = 1
        completed.append(ident)
        events.append('end:' + ident)
        active.remove(ident)
        if ident == 'b':
            b_done.set()
        return seen_version

    registry.register(scope, h.Tool('read', body, parallel=lambda _: True))
    registry.register(scope, h.Tool('write', body,
                                    parallel=lambda _: unsafe_exclusive))
    calls = [call('a'), call('b'), call('write', 'write'), call('c')]
    session.append('assistant/message', calls=calls)
    results = await h.run_batch(calls, registry, scope, session, limit=limit)
    committed = [e['data']['call_id'] for e in session.events
                 if e['type'] == 'tool/result']
    report = {
        'completion': completed,
        'naive_history': completed.copy(),  # Deliberately wrong proposed ordering.
        'settled_history': committed,
        'values': [row['value'] for row in results],
        'peak': peak,
        'overlaps': overlaps,
        'events': events,
    }
    assert committed == ['a', 'b', 'write', 'c']
    assert all(row['ok'] for row in results)
    assert peak <= limit
    if force_inversion:
        assert completed == ['b', 'a', 'write', 'c']
    if unsafe_exclusive:
        assert overlaps == [['c', 'write']]
        assert report['values'][-1] == 0
    else:
        assert overlaps == []
        assert report['values'] == [0, 0, 1, 1]
        assert events.index('end:a') < events.index('start:write')
        assert events.index('end:b') < events.index('start:write')
        assert events.index('end:write') < events.index('start:c')
    scope.close()
    return report


async def cancellation_case(pre_cancelled=False):
    scope, registry, session = h.Scope(), h.Registry(), h.Session()
    token, cleanup = h.CancelToken(pre_cancelled), []

    async def cancelling(args, token):
        token.cancelled = True
        await asyncio.sleep(0)
        cleanup.append('body finished')
        return 42

    registry.register(scope, h.Tool('cancel', cancelling))
    calls = [call('x', 'cancel'), call('y', 'cancel')]
    session.append('assistant/message', calls=calls)
    results = await h.run_batch(calls, registry, scope, session, token=token)
    report = {'cleanup': cleanup, 'codes': [r['code'] for r in results]}
    expected = (['ABORTED_BEFORE_DISPATCH'] * 2 if pre_cancelled else
                ['ABORTED', 'ABORTED_BEFORE_DISPATCH'])
    assert report['codes'] == expected
    assert cleanup == ([] if pre_cancelled else ['body finished'])
    scope.close()
    return report


def recovery_case():
    session = h.Session()
    calls = [call('z-unseen'), call('a-attempt')]
    session.append('assistant/message', calls=calls)
    session.append('tool/call', call_id='a-attempt', name='read')
    recovered = h.recover_missing(session)
    assert recovered == {'a-attempt': 'TOOL_OUTCOME_UNKNOWN',
                         'z-unseen': 'TOOL_NOT_STARTED'}
    assert h.pending_calls(session.surface()) == set()
    assert h.recover_missing(session) == {}
    return {'model_order': [c['id'] for c in calls],
            'recovery_order': list(recovered), 'codes': recovered,
            'pending_after': []}


async def main(args):
    if args.case == 'order':
        return await batch_case(force_inversion=True)
    if args.case == 'barrier':
        if args.unsafe_exclusive and args.limit != 2:
            raise ValueError('unsafe-exclusive comparison requires --limit 2')
        return await batch_case(limit=args.limit,
                                unsafe_exclusive=args.unsafe_exclusive)
    if args.case == 'cancel':
        return await cancellation_case(args.pre_cancelled)
    if args.case == 'recovery':
        return recovery_case()
    return {
        'order': await batch_case(force_inversion=True),
        'serial': await batch_case(limit=1),
        'unsafe_barrier': await batch_case(unsafe_exclusive=True),
        'cancel': await cancellation_case(),
        'pre_cancelled': await cancellation_case(True),
        'recovery': recovery_case(),
    }


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', nargs='?', default='all',
                        choices=['all', 'order', 'barrier', 'cancel', 'recovery'])
    parser.add_argument('--limit', type=int, default=2)
    parser.add_argument('--unsafe-exclusive', action='store_true')
    parser.add_argument('--pre-cancelled', action='store_true')
    args = parser.parse_args()
    try:
        result = asyncio.run(asyncio.wait_for(main(args), timeout=3.0))
    except TimeoutError:
        raise SystemExit('Experiment timed out after 3s. The order case makes a wait for b; '
                         'if classification serializes them, b cannot start. Restore explicit '
                         'parallel=True or run the barrier case. This timeout is a walkthrough '
                         'guard, not a production cancellation or rollback guarantee.')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    cli()
