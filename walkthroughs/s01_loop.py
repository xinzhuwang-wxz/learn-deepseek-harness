"""Observe the actual S01 snapshot. All calls are local and deterministic."""
import argparse
import json
from load_lesson import load

h = load('s01_loop')


def call(value=21, name='double'):
    return {'id': 'c1', 'name': name, 'args': {'value': value}}


def script(value=21, name='double'):
    return [{'calls': [call(value, name)]}, {'text': '42'}]


def feedback_case(value=21, name='double'):
    model = h.ScriptedModel(script(value, name))
    messages = h.run(model=model)
    result = messages[2]
    assert model.requests[1][-1] == result
    assert len(model.requests) == 2
    if name == 'double':
        assert result['content'] == {'ok': True, 'value': value * 2}
    else:
        assert result['content'] == {'ok': False, 'error': 'KeyError'}
    return {
        'request_lengths': [len(request) for request in model.requests],
        'second_request': model.requests[1],
        'history_roles': [message['role'] for message in messages],
        'scripted_final': messages[-1]['content']['text'],
    }


def blind_case():
    model = h.ScriptedModel(script())
    messages = [{'role': 'user', 'content': 'Double 21'}]
    first = model.respond(messages)
    final = model.respond(messages)
    saw_result = any(message['role'] == 'tool' for message in model.requests[1])
    assert first['calls'][0]['id'] == 'c1' and not saw_result
    assert final['text'] == '42'
    return {'request_lengths': [len(r) for r in model.requests],
            'second_request_saw_tool': saw_result, 'scripted_final': final['text']}


def stop_case():
    model = h.ScriptedModel([{'text': 'done'}, {'calls': [call()]}])
    messages = h.run(model=model)
    untouched = next(model.responses)
    assert len(model.requests) == 1 and untouched == {'calls': [call()]}
    return {'requests': len(model.requests),
            'history_roles': [m['role'] for m in messages],
            'next_unconsumed_call': untouched['calls'][0]['id']}


def budget_case(max_steps=1):
    model = h.ScriptedModel(script())
    try:
        messages = h.run(model=model, max_steps=max_steps)
        outcome = {'returned': True, 'last_role': messages[-1]['role']}
    except RuntimeError as exc:
        outcome = {'returned': False, 'error': str(exc)}
    assert outcome['returned'] is (max_steps >= 2)
    return {'max_steps': max_steps, 'requests': len(model.requests), **outcome}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', choices=['feedback', 'missing', 'blind', 'stop', 'budget', 'all'], nargs='?', default='all')
    parser.add_argument('--value', type=int, default=21)
    parser.add_argument('--max-steps', type=int, choices=[1, 2], default=1)
    args = parser.parse_args()
    cases = {'feedback': lambda: feedback_case(args.value),
             'missing': lambda: feedback_case(args.value, 'missing'),
             'blind': blind_case, 'stop': stop_case,
             'budget': lambda: budget_case(args.max_steps)}
    result = {name: fn() for name, fn in cases.items()} if args.case == 'all' else cases[args.case]()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
