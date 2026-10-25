"""Observe paired cuts and two coordinate systems in one local lesson."""
import argparse
import asyncio
import json
from load_lesson import load

h = load('s06_compaction')


async def completed_session():
    session, scope, registry = h.Session(), h.Scope(), h.Registry()
    session.append('user/message', text='Double 21')

    async def double(args, token):
        return args['value'] * 2

    registry.register(scope, h.Tool('double', double))
    calls = [{'id': 'c1', 'name': 'double', 'args': {'value': 21}}]
    model = h.ScriptedModel([{'calls': calls}, {'text': '42'}])
    await h.agent_loop(model, registry, scope, session)
    scope.close()
    return session


def positions(session):
    return [{'position': i, 'seq': e['seq'], 'type': e['type']}
            for i, e in enumerate(session.surface())]


async def boundary_case(count=2):
    session = await completed_session()
    before = session.events
    selected = session.surface()[:count]
    report = {'count': count, 'before': positions(session),
              'selected_seqs': [e['seq'] for e in selected],
              'pending_at_cut': sorted(h.pending_calls(selected))}
    try:
        seq = session.compact_prefix(count, 'Confirmed: double 21 is 42.')
    except ValueError as exc:
        report.update(accepted=False, error=str(exc))
        assert session.events == before
    else:
        report.update(accepted=True, replacement_seq=seq)
        assert session.events[:len(before)] == before
    report.update(log_before=len(before), log_after=len(session.events),
                  after=positions(session))
    assert report['accepted'] is (count in {1, 3, 4})
    return report


async def repeat_case():
    session = await completed_session()
    original = session.events
    first = session.compact_prefix(3, 'Confirmed: double 21 is 42.')
    first_surface = positions(session)
    session.append('user/message', text='Now explain why.')
    before_second = positions(session)
    second = session.compact_prefix(2, 'The completed answer is 42.')
    replacements = [e for e in session.events if e['type'] == 'surface/replace']
    replay = h.Session(session.events)
    assert replay.messages() == session.messages()
    assert session.events[:len(original)] == original
    assert replacements[0]['data']['seqs'] == [0, 2, 4]
    assert replacements[1]['data']['seqs'] == [9, 7]
    assert [e['seq'] for e in session.surface()] == [11, 10]
    return {'first_replacement_seq': first, 'first_surface': first_surface,
            'before_second': before_second, 'second_replacement_seq': second,
            'replaced_seqs': [e['data']['seqs'] for e in replacements],
            'after_second': positions(session), 'messages': session.messages(),
            'original_prefix_unchanged': session.events[:len(original)] == original,
            'replay_equal': replay.messages() == session.messages(),
            'log_count': len(session.events)}


async def semantic_case():
    session = await completed_session()
    confirmed = next(e['data']['value'] for e in session.events
                     if e['type'] == 'tool/result')
    wrong_summary = 'Confirmed: double 21 is 41.'
    session.compact_prefix(3, wrong_summary)
    model, scope = h.ScriptedModel([{'text': 'Received.'}]), h.Scope()
    await h.agent_loop(model, h.Registry(), scope, session)
    request = model.requests[0]
    result = {'confirmed_value_in_log': confirmed,
              'accepted_summary': request[0]['text'],
              'request': request,
              'pending_after': sorted(h.pending_calls(session.surface()))}
    assert confirmed == 42 and request[0]['text'] == wrong_summary
    assert result['pending_after'] == []
    scope.close()
    return result


async def main(args):
    if args.case == 'boundary':
        return await boundary_case(args.count)
    if args.case == 'repeat':
        return await repeat_case()
    if args.case == 'semantic':
        return await semantic_case()
    return {'cut_after_call': await boundary_case(2),
            'cut_after_result': await boundary_case(3),
            'repeat': await repeat_case(), 'semantic': await semantic_case()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', nargs='?', default='all',
                        choices=['all', 'boundary', 'repeat', 'semantic'])
    parser.add_argument('--count', type=int, choices=[1, 2, 3, 4], default=2)
    # Bound cooperative waits if an exercise later introduces one.
    print(json.dumps(asyncio.run(asyncio.wait_for(main(parser.parse_args()), 5)),
                     ensure_ascii=False, indent=2))
