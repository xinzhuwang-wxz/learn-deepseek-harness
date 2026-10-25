#!/usr/bin/env python3
"""Record actual deterministic teaching runs for web replay and print tables."""
import asyncio,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from examples.harness import *
from examples.scenarios import double,call

async def build():
    cases=[]
    for ident,title,mode in [('allowed','允许后执行并回灌','allow'),('denied','没有审批通道时拒绝','ask'),('cancelled','取消后保留完整结算','cancel')]:
        session=Session();scope=Scope();registry=Registry()
        async def body(args,token):
            if mode=='cancel':token.cancelled=True
            await asyncio.sleep(0)
            return args['value']*2
        registry.register(scope,Tool('double',body,parallel=lambda _:True))
        session.append('user/message',text='Double 21')
        await agent_loop([{'calls':[call()]},{'text':'Final response after observing tool result.'}],registry,scope,session,policy=Policy(decide=lambda _: 'ask' if mode=='ask' else 'allow'))
        cases.append((ident,title,session))
    session=Session();session.append('user/message',text='Two requests before a simulated crash')
    session.append('assistant/message',calls=[call('a'),call('b')]);session.append('tool/call',call_id='a',name='double');recover_missing(session)
    cases.append(('unknown','重放区分未开始与结果未知',session))
    session=Session();session.append('user/message',text='Double 21');session.append('assistant/message',calls=[call()]);session.append('tool/call',call_id='c1',name='double');session.append('tool/result',call_id='c1',ok=True,value=42);session.append('assistant/message',text='42');session.compact_prefix(3,'Confirmed result: 42')
    cases.append(('compact','替换可见面而保留原日志',session))
    result=[]
    for ident,title,session in cases:
        frames=[]
        for i,event in enumerate(session.events):
            visible=Session(session.events[:i+1]).messages()
            frames.append({'event':event,'visible_messages':visible,'durable_count':i+1,'visible_count':len(visible)})
        result.append({'id':ident,'title':title,'frames':frames})
    (ROOT/'assets/trace-data.js').write_text('window.HARNESS_TRACES = '+json.dumps(result,ensure_ascii=False)+';\n')
    (ROOT/'output').mkdir(exist_ok=True)
    (ROOT/'output/traces.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    lines=['# 轨迹实验室','', '这不是实时模型，也不会在浏览器执行 Python。下面的逐步回放来自 scripts/build_traces.py 实际运行本项目教学代码生成的固定轨迹。改变代码后重新生成，才会改变轨迹。每个事件同时展示日志事实和模型可见消息。','',
'''<div class="trace-lab" data-trace-lab>
<label for="trace-case">选择实验</label><select id="trace-case" aria-label="选择实验"></select>
<div class="trace-controls"><button id="trace-prev">上一步</button><button id="trace-next">下一步</button><button id="trace-reset">重置</button><span id="trace-position" aria-live="polite"></span></div>
<div class="trace-grid"><section><h3>已提交的事件</h3><pre id="trace-event"></pre></section><section><h3>此时模型可见的历史</h3><pre id="trace-projection"></pre></section></div>
<p id="trace-observation" aria-live="polite"></p>
</div>''','', '## 怎样观察','', '先预测，再点下一步。tool/call 出现时，能否认定工具已经成功？不能。遇到 step/start，模型消息数量会增加吗？不会。surface/replace 之后，为什么日志条数增加，可见消息反而减少？因为原事实保留，投影变了。','', '以下为同一批轨迹的静态表格。关闭 JavaScript 仍可阅读，下载 Markdown 后也能完成核心观察。','']
    for case in result:
        lines+=['## '+case['title'],'','| seq | 事件 | 可见消息数 | 关键事实 |','|---|---|---|---|']
        for f in case['frames']:
            e=f['event'];d=e['data'];fact=d.get('code',str(d.get('value','')))
            if e['type']=='tool/call':fact='记录调用，不代表成功'
            if e['type']=='surface/replace':fact='原日志保留；可见面被替换'
            if 'calls' in d:fact='请求 '+','.join(c['id'] for c in d['calls'])
            lines.append(f"| {e['seq']} | {e['type']} | {f['visible_count']} | {fact} |")
        lines.append('')
    lines+=['## 故障挑战','', '把恢复逻辑中的 UNKNOWN 错写为 NOT_STARTED，再运行对应测试。测试应失败，而不是修改预期值迎合实现。再把结果按完成顺序提交，运行有序结算测试，解释为什么看似更快的展示可能破坏稳定历史。','', '教学轨迹没有计入真实网络延迟、token 数、GPU 时间或生产吞吐率。不要把事件序号解释成毫秒，也不要从这里推断上游性能。','']
    (ROOT/'docs/11-traces.md').write_text('\n'.join(lines))
asyncio.run(build())
