"""Observe independent event prefixes, explicit return, and monotone depth."""
import argparse
import asyncio
import json
from load_lesson import load

h = load('s08_subagents')


async def completed_session():
    parent, scope, registry = h.Session(), h.Scope(), h.Registry()
    parent.append('user/message', text='Double 21')

    async def double(args, token):
        return args['value'] * 2

    registry.register(scope, h.Tool('double', double))
    calls = [{'id': 'c1', 'name': 'double', 'args': {'value': 21}}]
    await h.agent_loop([{'calls': calls}, {'text': '42'}], registry, scope, parent)
    scope.close()
    return parent


def result_boundary(session):
    return next(e['seq'] for e in session.events if e['type'] == 'tool/result')


async def delegation_case():
    parent = await completed_session()
    original = parent.events
    boundary = result_boundary(parent)
    child = parent.fork(boundary)
    inherited_count = len(child.events)
    task = 'Explain the verified result; use no tools; return one sentence.'
    child.append('user/message', text=task)
    value = next(m['value'] for m in child.messages() if m['role'] == 'tool')
    model = h.ScriptedModel([{'text': f'Doubling 21 gives the verified result {value}.'}])
    child_scope = h.Scope()
    await h.agent_loop(model, h.Registry(), child_scope, child,
                       policy=h.Policy(decide=lambda _: 'deny'))
    unchanged = parent.events == original
    summary = child.messages()[-1]['text']
    parent.append('assistant/message', text=summary, source='child-summary',
                  child_depth=child.depth)
    report = {'fork_boundary_seq': boundary, 'inherited_count': inherited_count,
              'child_depth': child.depth, 'child_request': model.requests[0],
              'parent_unchanged_before_return': unchanged,
              'parent_has_child_task': any(e['data'].get('text') == task
                                           for e in parent.events),
              'parent_before_count': len(original),
              'parent_after_count': len(parent.events), 'child_count': len(child.events),
              'parent_return_event': parent.events[-1]}
    assert unchanged and not report['parent_has_child_task']
    assert child.events[:inherited_count] == original[:boundary + 1]
    assert len(parent.events) == len(original) + 1
    child_scope.close()
    return report


async def boundary_case():
    parent = await completed_session()
    call_seq = next(e['seq'] for e in parent.events if e['type'] == 'assistant/message'
                    and e['data'].get('calls'))
    rows = []
    for boundary in [call_seq, result_boundary(parent)]:
        try:
            child = parent.fork(boundary)
        except ValueError as exc:
            rows.append({'boundary_seq': boundary, 'accepted': False, 'error': str(exc)})
        else:
            rows.append({'boundary_seq': boundary, 'accepted': True,
                         'inherited_count': len(child.events)})
    assert [row['accepted'] for row in rows] == [False, True]
    return {'visible_seqs': [e['seq'] for e in parent.surface()], 'cuts': rows}


async def depth_case():
    original = await completed_session()
    saved_events, saved_depth = original.events, 2
    restored = h.Session(saved_events, depth=saved_depth)
    boundary = result_boundary(restored)
    rows = []
    for runtime, maximum in [(0, 2), (0, 3), (4, 5)]:
        try:
            child = restored.fork(boundary, runtime_depth=runtime, max_depth=maximum)
        except ValueError as exc:
            rows.append({'saved': restored.depth, 'runtime': runtime, 'max': maximum,
                         'accepted': False, 'error': str(exc)})
        else:
            rows.append({'saved': restored.depth, 'runtime': runtime, 'max': maximum,
                         'accepted': True, 'child_depth': child.depth})
    missing_metadata = h.Session(saved_events)
    restarted = missing_metadata.fork(boundary)
    assert [row['accepted'] for row in rows] == [False, True, True]
    assert [rows[1]['child_depth'], rows[2]['child_depth']] == [3, 5]
    assert restarted.depth == 1
    return {'cases': rows, 'without_depth_metadata': restarted.depth,
            'event_log_contains_depth': any('depth' in e['data'] for e in saved_events)}


async def snapshot_case():
    parent = await completed_session()
    original = parent.events
    child = parent.fork(result_boundary(parent))
    borrowed = child.events
    borrowed[0]['data']['text'] = 'changed outside'
    parent.append('user/message', text='Parent-only follow-up')
    child.append('user/message', text='Child-only follow-up')
    result = {'parent_first': parent.events[0]['data']['text'],
              'child_first': child.events[0]['data']['text'],
              'parent_tail': parent.messages()[-1]['text'],
              'child_tail': child.messages()[-1]['text'],
              'parent_original_prefix_unchanged': parent.events[:len(original)] == original}
    assert result['parent_first'] == result['child_first'] == 'Double 21'
    assert result['parent_tail'] != result['child_tail']
    assert result['parent_original_prefix_unchanged']
    return result


async def siblings_case():
    parent = await completed_session()
    boundary = result_boundary(parent)
    children = [parent.fork(boundary, max_depth=1) for _ in range(3)]
    rejected = []
    for child in children:
        try:
            child.fork(boundary, max_depth=1)
        except ValueError as exc:
            rejected.append(str(exc))
    depths = [child.depth for child in children]
    assert depths == [1, 1, 1] and len(rejected) == 3
    return {'sibling_depths': depths, 'children_created': len(children),
            'grandchild_errors': rejected}


async def alias_case():
    parent = await completed_session()
    before = len(parent.events)
    child = parent  # Deliberately wrong: another name for the same Session.
    child.append('user/message', text='Child-only work leaked into parent')
    report = {'same_object': child is parent, 'parent_before_count': before,
              'parent_after_count': len(parent.events),
              'parent_tail': parent.messages()[-1]['text']}
    assert report['same_object'] and len(parent.events) == before + 1
    return report


async def main(args):
    cases = {'delegation': delegation_case, 'boundary': boundary_case,
             'depth': depth_case, 'snapshot': snapshot_case, 'siblings': siblings_case,
             'alias': alias_case}
    if args.case != 'all':
        return await cases[args.case]()
    return {name: await run() for name, run in cases.items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', nargs='?', default='all',
                        choices=['all', 'delegation', 'boundary', 'depth', 'snapshot', 'siblings', 'alias'])
    # Bound cooperative waits if an exercise later introduces one.
    print(json.dumps(asyncio.run(asyncio.wait_for(main(parser.parse_args()), 5)),
                     ensure_ascii=False, indent=2))
