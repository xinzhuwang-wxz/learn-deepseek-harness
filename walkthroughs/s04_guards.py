"""In-memory permission decisions around one double(21) call."""
import argparse
import asyncio
import json
from load_lesson import load

h = load('s04_guards')


async def experiment(case, value=21):
    scope, registry, session = h.Scope(), h.Registry(), h.Session()
    trace, body_calls = [], 0

    async def double(args, token):
        nonlocal body_calls
        body_calls += 1
        trace.append('body')
        return args['value'] * 2

    def decide(call):
        trace.append('decide')
        if case == 'policy-error':
            raise RuntimeError('policy unavailable')
        return 'deny' if case == 'deny' else 'ask'

    def approve(call):
        trace.append('approve')
        return 'yes' if case == 'truthy' else True

    def guard(call):
        trace.append('guard')
        if case == 'guard':
            return 'owner boundary'
        if case == 'false-guard':
            return False  # Deliberate contract violation: only None means pass.
        return None

    def validate(args):
        trace.append('validate')
        number = args.get('value')
        return type(number) is int and (case != 'range' or 0 <= number <= 100)

    policy = h.Policy(decide=decide,
                      approve=None if case == 'missing' else approve,
                      guards=(guard,))
    registry.register(scope, h.Tool('double', double, validate=validate))
    call = {'id': 'c1', 'name': 'double', 'args': {'value': value}}
    session.append('assistant/message', calls=[call])
    if case == 'unguarded':
        result = {'ok': True, 'value': await double(call['args'], h.CancelToken())}
    else:
        result = (await h.run_batch([call], registry, scope, session, policy))[0]
    report = {'input': call, 'trace': trace, 'body_calls': body_calls,
              'result': result, 'event_types': [e['type'] for e in session.events]}
    assert body_calls == (1 if result['ok'] else 0)
    if case != 'unguarded':
        assert report['event_types'] == ['assistant/message', 'tool/call', 'tool/result']
    scope.close()
    return report


async def main(args):
    if args.case == 'mutating-validator':
        return await mutating_validator()
    if args.case != 'all':
        return await experiment(args.case, args.value)
    results = {}
    for case in ('unguarded', 'missing', 'truthy', 'deny', 'guard',
                 'false-guard', 'policy-error', 'allowed'):
        results[case] = await experiment(case)
    results['invalid'] = await experiment('allowed', '21')
    results['range'] = await experiment('range', 101)
    expected = {'missing': 'DENIED', 'truthy': 'DENIED', 'deny': 'DENIED',
                'guard': 'GUARD_DENIED', 'false-guard': 'GUARD_DENIED',
                'policy-error': 'POLICY_ERROR', 'invalid': 'INVALID_ARGUMENTS',
                'range': 'INVALID_ARGUMENTS'}
    for case, code in expected.items():
        assert results[case]['result']['code'] == code
    assert results['allowed']['result']['value'] == 42
    assert results['unguarded']['body_calls'] == 1
    results['mutating-validator'] = await mutating_validator()
    return results


async def mutating_validator():
    scope, registry, session = h.Scope(), h.Registry(), h.Session()
    observed = []

    def validate(args):
        args['value'] = 999  # Deliberately violates the pure-check contract.
        return True

    async def double(args, token):
        observed.append(args['value'])
        return args['value'] * 2

    call = {'id': 'c1', 'name': 'double', 'args': {'value': 21}}
    registry.register(scope, h.Tool('double', double, validate=validate))
    session.append('assistant/message', calls=[call])
    result = (await h.run_batch([call], registry, scope, session))[0]
    report = {'caller_value': call['args']['value'], 'body_values': observed,
              'result': result}
    assert report['caller_value'] == 21 and observed == [999]
    assert result['value'] == 1998
    scope.close()
    return report


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', nargs='?', default='all', choices=[
        'all', 'unguarded', 'missing', 'truthy', 'deny', 'guard',
        'false-guard', 'policy-error', 'allowed', 'range', 'mutating-validator'])
    parser.add_argument('--value', type=json.loads, default=21,
                        help='JSON value, such as 21, -1, true or "21"')
    args = parser.parse_args()
    try:
        result = asyncio.run(asyncio.wait_for(main(args), timeout=3.0))
    except TimeoutError:
        raise SystemExit('Walkthrough exceeded 3s. Check for an await that never finishes; '
                         'this guard does not promise rollback or stop synchronous code.')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    cli()
