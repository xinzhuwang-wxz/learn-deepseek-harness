#!/usr/bin/env python3
"""Generate independently runnable cumulative lessons from original authored blocks.

No upstream source is imported. AST selection prevents later mechanisms leaking
into earlier snapshots. Generated code is checked in for direct reading/running.
"""
import ast
from pathlib import Path
import difflib
import json
ROOT = Path(__file__).resolve().parents[1]
source = (ROOT/'examples/harness.py').read_text()
tree = ast.parse(source)
blocks = {node.name: ast.get_source_segment(source, node) for node in tree.body if isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef))}
# AST source segments start at class/def, so retain explicit dataclass decorators.
for name, decorator in [('Scope','@dataclass(eq=False)'),('Tool','@dataclass'),('CancelToken','@dataclass'),('Policy','@dataclass')]:
    blocks[name] = decorator+'\n'+blocks[name]

def session_for(stage):
    node = ast.parse(blocks['Session']).body[0]
    allowed = {'__init__','events','append','surface','messages'}
    if stage >= 6: allowed.add('compact_prefix')
    if stage >= 8: allowed.add('fork')
    node.body = [n for n in node.body if getattr(n,'name','') in allowed]
    if stage < 8:
        for member in node.body:
            if getattr(member,'name','') == '__init__':
                member.args.args = member.args.args[:-1]
                member.args.defaults = member.args.defaults[:-1]
                member.body = member.body[2:]
    if stage < 6:
        # Earlier projection has no surface replacement mechanism yet.
        for member in node.body:
            if getattr(member,'name','') == 'surface':
                member.body = ast.parse("return snapshot([e for e in self._events if e['type'] in {'user/message', 'assistant/message', 'tool/result'}])").body
    return ast.unparse(node)

base_imports = '''import asyncio
from dataclasses import dataclass, field
import json
from typing import Any, Awaitable, Callable
'''
plain_batch = '''async def run_batch(calls, registry, scope, session, policy=None, token=None, limit=1):
    results = []
    for call in calls:
        tool = registry.get(call['name'], scope)
        session.append('tool/call', call_id=call['id'], name=call['name'])
        try:
            if tool is None: raise ValueError('unknown tool')
            value = await tool.body(call['args'], CancelToken())
            outcome = {'ok': True, 'value': value}
        except Exception as exc:
            outcome = {'ok': False, 'error': type(exc).__name__}
        session.append('tool/result', call_id=call['id'], **outcome)
        results.append(outcome)
    return results
'''
serial_batch = blocks['run_batch'].replace('limit=2','limit=1')
start = serial_batch.index('        if parallel_safe(first, group[0]["args"]):')
end = serial_batch.index('        # Preserve order;',start)
serial_batch = serial_batch[:start]+serial_batch[end:]
serial_batch = serial_batch.replace('Bounded waves + exclusive barriers. Not upstream\'s rolling-pool scheduler.','Serial guarded execution; the next lesson adds scheduling.')

stage_names = ['s01_loop','s02_events','s03_plugins','s04_guards','s05_settlement','s06_compaction','s07_skills','s08_subagents']
meta=[]
for stage,name in enumerate(stage_names,1):
    folder=ROOT/'lessons'/name; folder.mkdir(parents=True,exist_ok=True)
    if stage == 1:
        text=(ROOT/'examples/s01_loop.py').read_text()
    else:
        parts = [f'"""Stage {stage}: original offline teaching snapshot; not the dsh runtime."""', 'from __future__ import annotations',base_imports,blocks['snapshot'],blocks['ScriptedModel'],session_for(stage)]
        if stage >= 6: parts.append(blocks['pending_calls'])
        if stage >= 3:
            parts += [blocks[n] for n in ['Scope','Tool','Registry','CancelToken']]
            if stage >= 4: parts.append(blocks['Policy'])
            if stage >= 5: parts.extend([blocks['parallel_safe'], blocks['recover_missing']])
            # Recovery depends on pairing before full compaction is taught.
            if stage == 5: parts.append(blocks['pending_calls'])
            parts.append(plain_batch if stage==3 else serial_batch if stage==4 else blocks['run_batch'])
            parts.append(blocks['agent_loop'])
        if stage >= 7: parts.append(blocks['SkillCatalog'])
        demo = '''async def demo():
    session = Session()
    session.append('user/message', text='Double 21')
'''
        if stage==2:
            parts.append('''def run(script, session, max_steps=4):
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
''')
            demo += '''    run([{'calls': [{'id': 'c1', 'name': 'double', 'args': {'value': 21}}]}, {'text': '42'}], session)
    return {'event_types': [e['type'] for e in session.events], 'model_messages': session.messages()}
'''
        else:
            demo += '''    root, registry = Scope(), Registry()
    async def double(args, token): return args['value'] * 2
    registry.register(root, Tool('double', double, validate=lambda a: type(a.get('value')) is int,
                                  parallel=lambda _: True))
    calls = [{'id': 'c1', 'name': 'double', 'args': {'value': 21}}]
'''
            if stage==4:
                demo += '''    session.append('assistant/message', calls=calls)
    results = await run_batch(calls, registry, root, session, Policy(decide=lambda _: 'ask'))
    return {'approval_channel': 'absent', 'result': results[0]}
'''
            elif stage==5:
                demo += '''    calls.append({'id': 'c2', 'name': 'double', 'args': {'value': 3}})
    session.append('assistant/message', calls=calls)
    results = await run_batch(calls, registry, root, session, limit=2)
    return {'model_order': [r['call_id'] for r in results], 'values': [r['value'] for r in results]}
'''
            else:
                demo += '''    await agent_loop([{'calls': calls}, {'text': '42'}], registry, root, session)
'''
                if stage==3:
                    demo+='''    visible_before = registry.get('double', root) is not None
    root.close()
    return {'visible_before': visible_before, 'removed_after_dispose': registry.get('double', root) is None}
'''
                elif stage==6:
                    demo+='''    before = len(session.events)
    session.compact_prefix(3, 'Confirmed: double 21 is 42.')
    return {'log_before': before, 'log_after': len(session.events), 'surface_count': len(session.messages())}
'''
                elif stage==7:
                    demo+='''    catalog = SkillCatalog()
    catalog.register('explain', 'Explain a verified result', 'Show the input, operation, and confirmed output.')
    index = catalog.list()
    before = catalog.loads
    body = catalog.load('explain')
    return {'index': index, 'loads_before': before, 'loads_after': catalog.loads, 'body': body}
'''
                else:
                    demo+='''    child = session.fork(len(session.events)-1)
    child.append('user/message', text='Explain 42')
    return {'parent_events': len(session.events), 'child_events': len(child.events), 'child_depth': child.depth}
'''
        parts.append(demo)
        parts.append("if __name__ == '__main__':\n    print(json.dumps(asyncio.run(demo()), ensure_ascii=False, indent=2))")
        text='\n\n'.join(parts)+'\n'
    (folder/'code.py').write_text(text)
    meta.append({'id':name,'stage':stage,'lines':len(text.splitlines())})
    if stage>1:
        previous=(ROOT/'lessons'/stage_names[stage-2]/'code.py').read_text()
        patch=''.join(difflib.unified_diff(previous.splitlines(True),text.splitlines(True),fromfile=stage_names[stage-2]+'/code.py',tofile=name+'/code.py'))
        (folder/'delta.patch').write_text(patch)
(ROOT/'lessons/manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps(meta,indent=2))

# Explicit regeneration also refreshes the optional full-code reading appendix.
text=['# 可独立运行的代码册','','下面收录最小 S01 和最终 S08 的完整原创建模代码。中间阶段在 lessons/ 中各有独立文件与相邻差异；网页每课顶部可下载。这里按固定行段展示，便于逐段对照，行号写在标题而不是代码正文中。合并同一程序各段即可还原对应 code.py。','']
for name,title in [('s01_loop','S01 最小循环'),('s08_subagents','S08 累计系统')]:
    lines=(ROOT/'lessons'/name/'code.py').read_text().splitlines()
    text+=['## '+title,'',f'运行：python3 lessons/{name}/code.py。共 {len(lines)} 行。','']
    for i in range(0,len(lines),36):
        text += [f'### 第 {i+1} 至 {min(i+36,len(lines))} 行','','```python',*lines[i:i+36],'```','']
(ROOT/'docs/13-codebook.md').write_text('\n'.join(text))
