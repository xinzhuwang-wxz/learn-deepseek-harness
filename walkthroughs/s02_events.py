"""Observe S02 event projections, snapshots, and in-memory reconstruction."""
import argparse
import json
from load_lesson import load

h = load('s02_events')


def filled_session():
    session = h.Session()
    session.append('user/message', text='Double 21')
    script = [{'calls': [{'id': 'c1', 'name': 'double', 'args': {'value': 21}}]},
              {'text': '42'}]
    h.run(script, session)
    return session


def projection_case():
    session = filled_session()
    events, surface, messages = session.events, session.surface(), session.messages()
    audit = [e for e in events if e['type'] in {'tool/call', 'tool/result'}]
    assert len(events) == 9 and len(messages) == 4
    assert [e['seq'] for e in surface] == [0, 2, 4, 7]
    assert [e['seq'] for e in audit] == [3, 4]
    assert messages[2] == {'role': 'tool', 'call_id': 'c1', 'ok': True, 'value': 42}
    return {'log': [{'seq': e['seq'], 'type': e['type']} for e in events],
            'surface_seq': [e['seq'] for e in surface],
            'model_messages': messages, 'audit_seq': [e['seq'] for e in audit]}


def snapshot_case():
    data = {'items': [1]}
    unsafe = [{'type': 'user/message', 'data': data}]
    session = h.Session()
    assigned = session.append('user/message', **data)
    data['items'].append(2)
    after_input_edit = session.events[0]['data']['items']
    read = session.events
    read[0]['data']['items'].append(3)
    read.append({'seq': 1, 'type': 'forged', 'data': {}})
    message_view = session.messages()
    message_view[0]['items'].append(4)
    assert after_input_edit == [1]
    assert session.events[0]['data']['items'] == [1] and len(session.events) == 1
    return {'assigned_seq': assigned, 'unsafe_alias_items': unsafe[0]['data']['items'],
            'after_input_edit': after_input_edit, 'edited_read_items': read[0]['data']['items'],
            'edited_message_items': message_view[0]['items'],
            'stored_items': session.events[0]['data']['items'], 'stored_event_count': len(session.events)}


def replay_case():
    original = filled_session()
    exported = original.events
    replay = h.Session(exported)
    before = original.messages()
    replay_equal = replay.messages() == before
    exported[0]['data']['text'] = 'external edit'
    replay.append('user/message', text='next question')
    assert replay_equal and original.messages() == before
    assert replay.messages()[0]['text'] == 'Double 21'
    return {'same_messages_before_append': replay_equal,
            'original_events': len(original.events), 'replay_events': len(replay.events),
            'replay_first_text': replay.messages()[0]['text'],
            'replay_last_seq': replay.events[-1]['seq']}


def corrupt_case():
    events = filled_session().events
    events[4]['seq'] = 99
    try:
        h.Session(events)
    except ValueError as exc:
        return {'changed_position': 4, 'changed_seq': events[4]['seq'],
                'error': type(exc).__name__, 'message': str(exc)}
    raise AssertionError('non-contiguous sequence was accepted')


def json_case():
    errors = {}
    for name, value in [('nan', float('nan')), ('set', {1})]:
        try:
            h.snapshot({'value': value})
        except (TypeError, ValueError) as exc:
            errors[name] = type(exc).__name__
    assert errors == {'nan': 'ValueError', 'set': 'TypeError'}
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=['projection', 'snapshot', 'replay', 'corrupt', 'json', 'all'], nargs='?', default='all')
    args = parser.parse_args()
    cases = {'projection': projection_case, 'snapshot': snapshot_case, 'replay': replay_case,
             'corrupt': corrupt_case, 'json': json_case}
    result = {name: fn() for name, fn in cases.items()} if args.case == 'all' else cases[args.case]()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
