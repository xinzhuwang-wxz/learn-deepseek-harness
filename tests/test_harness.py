import asyncio
import importlib.util
import json
from pathlib import Path
import unittest

from examples.harness import (Session, pending_calls, recover_missing, Scope, Tool, Registry,
                              CancelToken, Policy, parallel_safe, run_batch, SkillCatalog,
                              agent_loop, snapshot, ScriptedModel)
from examples.s01_loop import run
from examples.scenarios import call, double, capstone

class SessionTests(unittest.TestCase):
    def test_snapshot_detaches_input_and_output(self):
        data={'items':[1]}; s=Session(); s.append('user/message', **data)
        data['items'].append(2); read=s.events; read[0]['data']['items'].append(3)
        self.assertEqual(s.events[0]['data']['items'],[1])
    def test_snapshot_rejects_nonfinite(self):
        with self.assertRaises(ValueError): snapshot({'x':float('nan')})
    def test_sequence_validation(self):
        with self.assertRaises(ValueError): Session([{'seq':1,'type':'user/message','data':{}}])
    def test_projection_omits_lifecycle(self):
        s=Session();s.append('step/start',step=0);s.append('user/message',text='hi')
        self.assertEqual(s.messages(),[{'role':'user','text':'hi'}])
    def pair(self):
        s=Session();s.append('user/message',text='task');s.append('assistant/message',calls=[call()]);s.append('tool/result',call_id='c1',ok=True,value=42);return s
    def test_unbalanced_compaction_is_rejected(self):
        with self.assertRaises(ValueError): self.pair().compact_prefix(2,'summary')
    def test_compaction_keeps_log(self):
        s=self.pair();old=s.events;s.compact_prefix(3,'summary')
        self.assertEqual(s.events[:3],old);self.assertEqual(len(s.messages()),1)
    def test_repeat_compaction_uses_visible_positions(self):
        s=self.pair();s.compact_prefix(3,'first');s.append('user/message',text='more');s.compact_prefix(2,'second')
        self.assertEqual(s.messages()[0]['text'],'second')
    def test_orphan_result_rejected(self):
        s=Session();s.append('tool/result',call_id='none')
        with self.assertRaises(ValueError): pending_calls(s.events)
    def test_duplicate_call_rejected(self):
        s=Session();s.append('assistant/message',calls=[call(),call()])
        with self.assertRaises(ValueError): pending_calls(s.events)
    def test_recovery_distinguishes_outcomes(self):
        s=Session();s.append('assistant/message',calls=[call('a'),call('b')]);s.append('tool/call',call_id='a')
        self.assertEqual(recover_missing(s),{'a':'TOOL_OUTCOME_UNKNOWN','b':'TOOL_NOT_STARTED'})
        self.assertEqual(recover_missing(s),{})
    def test_fork_is_independent(self):
        s=self.pair();child=s.fork(2);child.append('user/message',text='new')
        self.assertEqual(len(s.events),3);self.assertEqual(child.depth,1)
    def test_fork_rejects_open_pair(self):
        with self.assertRaises(ValueError): self.pair().fork(1)
    def test_saved_depth_cannot_be_reset(self):
        s=self.pair();s.depth=2
        with self.assertRaises(ValueError): s.fork(2,runtime_depth=0,max_depth=2)
    def test_negative_depth_rejected(self):
        with self.assertRaises(ValueError): Session(depth=-1)

class RegistryTests(unittest.TestCase):
    def test_scope_inheritance_and_no_sibling_leak(self):
        root=Scope();a=Scope(root);b=Scope(root);r=Registry();t=Tool('double',double);r.register(a,t)
        self.assertIs(r.get('double',a),t);self.assertIsNone(r.get('double',b))
    def test_child_override_disposal_restores_parent(self):
        root=Scope();child=Scope(root);r=Registry();old=Tool('x',double);new=Tool('x',double)
        r.register(root,old);r.register(child,new);self.assertIs(r.get('x',child),new)
        child.close();child.close();self.assertIs(r.get('x',child),old)
    def test_stale_disposer_preserves_new_registration(self):
        scope=Scope();r=Registry();old=Tool('x',double);new=Tool('x',double)
        dispose=r.register(scope,old);r.register(scope,new);dispose();self.assertIs(r.get('x',scope),new)
    def test_disposed_scope_cannot_register(self):
        scope=Scope();scope.close()
        with self.assertRaises(RuntimeError): Registry().register(scope,Tool('x',double))
    def test_reverse_cleanup_order(self):
        scope=Scope();seen=[];scope.owns(lambda:seen.append(1));scope.owns(lambda:seen.append(2));scope.close()
        self.assertEqual(seen,[2,1])
    def test_skills_are_lazy(self):
        c=SkillCatalog();c.register('x','short','body');c.list();self.assertEqual(c.loads,0);self.assertEqual(c.load('x'),'body');self.assertEqual(c.loads,1)

class AsyncTests(unittest.IsolatedAsyncioTestCase):
    def setup_case(self,body=double,parallel=lambda _:True,validate=lambda _:True):
        r=Registry();s=Scope();log=Session();r.register(s,Tool('double',body,validate,parallel));return r,s,log
    async def test_success(self):
        r,s,l=self.setup_case();out=await run_batch([call()],r,s,l);self.assertEqual(out[0]['value'],42)
    async def test_no_approval_channel_denies(self):
        executed=[]
        async def body(a,t): executed.append(1)
        r,s,l=self.setup_case(body);out=await run_batch([call()],r,s,l,Policy(decide=lambda _:'ask'))
        self.assertEqual(out[0]['code'],'DENIED');self.assertEqual(executed,[])
    async def test_guard_cannot_be_overridden_by_approval(self):
        r,s,l=self.setup_case();p=Policy(lambda _:'ask',lambda _:True,(lambda _:'owner says no',))
        self.assertEqual((await run_batch([call()],r,s,l,p))[0]['code'],'GUARD_DENIED')
    async def test_policy_exception_fails_closed(self):
        r,s,l=self.setup_case();p=Policy(lambda _:1/0)
        self.assertEqual((await run_batch([call()],r,s,l,p))[0]['code'],'POLICY_ERROR')
    async def test_validation(self):
        r,s,l=self.setup_case(validate=lambda _:False)
        self.assertEqual((await run_batch([call()],r,s,l))[0]['code'],'INVALID_ARGUMENTS')
    async def test_unknown_tool(self):
        r,s,l=self.setup_case()
        self.assertEqual((await run_batch([call(name='missing')],r,s,l))[0]['code'],'UNKNOWN_TOOL')
    async def test_explicit_true_only(self):
        self.assertFalse(parallel_safe(Tool('x',double,parallel=lambda _:'yes'),{}))
        self.assertFalse(parallel_safe(Tool('x',double,parallel=lambda _:1/0),{}))
    async def test_results_stay_model_order(self):
        finished=[]
        async def body(a,t):
            await asyncio.sleep(a['delay']);finished.append(a['name']);return a['name']
        r,s,l=self.setup_case(body)
        calls=[{'id':'a','name':'double','args':{'delay':.02,'name':'slow'}},{'id':'b','name':'double','args':{'delay':0,'name':'fast'}}]
        out=await run_batch(calls,r,s,l)
        self.assertEqual(finished,['fast','slow']);self.assertEqual([o['call_id'] for o in out],['a','b'])
    async def test_parallel_bound_and_exclusive_barrier(self):
        active=0;peak=0;violations=[]
        async def body(a,t):
            nonlocal active,peak
            if a['write'] and active:violations.append('write overlaps')
            active+=1;peak=max(peak,active);await asyncio.sleep(.002);active-=1;return True
        r,s,l=self.setup_case(body,parallel=lambda a:not a['write'])
        cs=[{'id':str(i),'name':'double','args':{'write':i==2}} for i in range(5)]
        await run_batch(cs,r,s,l,limit=2);self.assertEqual(violations,[]);self.assertEqual(peak,2)
    async def test_cancel_before_start(self):
        r,s,l=self.setup_case();out=await run_batch([call()],r,s,l,token=CancelToken(True))
        self.assertEqual(out[0]['code'],'ABORTED_BEFORE_DISPATCH')
    async def test_cancel_drains_started_body(self):
        done=[]
        async def body(a,t):t.cancelled=True;await asyncio.sleep(0);done.append(1);return 42
        r,s,l=self.setup_case(body);out=await run_batch([call()],r,s,l)
        self.assertEqual(done,[1]);self.assertEqual(out[0]['code'],'ABORTED')
    async def test_failed_body_normalized(self):
        async def bad(a,t):raise RuntimeError('simulated')
        r,s,l=self.setup_case(bad);self.assertEqual((await run_batch([call()],r,s,l))[0]['code'],'TOOL_ERROR')
    async def test_invalid_parallel_limit(self):
        r,s,l=self.setup_case()
        for bad in [0,-1,True,1.5]:
            with self.assertRaises(ValueError): await run_batch([call()],r,s,l,limit=bad)
    async def test_loop_ends_without_more_model_requests(self):
        r,s,l=self.setup_case();await agent_loop([{'text':'done'},{'calls':[call()]}],r,s,l)
        self.assertEqual(len([e for e in l.events if e['type']=='assistant/message']),1)
    async def test_next_model_request_contains_tool_result(self):
        r,s,l=self.setup_case();l.append('user/message',text='task')
        model=ScriptedModel([{'calls':[call()]},{'text':'done'}])
        await agent_loop(model,r,s,l)
        self.assertEqual(model.requests[1][-1]['role'],'tool')
        self.assertEqual(model.requests[1][-1]['value'],42)
        self.assertEqual(len(model.requests),2)
    async def test_capstone(self):
        result = await capstone()
        self.assertEqual(result, {
            'value': 42, 'durable_events_before_compaction': 9,
            'durable_events_after_compaction': 10, 'visible_messages': 2,
            'child_depth': 1, 'parent_unchanged_after_child_write': True,
            'tool_removed_after_dispose': True,
        })

class LessonTests(unittest.TestCase):
    def test_s01_stops_and_budget(self):
        self.assertEqual(run()[-1]['content']['text'],'42')
        with self.assertRaises(RuntimeError):run([{'calls':[call()]}]*5,max_steps=1)
    def test_generated_lesson_boundaries(self):
        root=Path(__file__).resolve().parents[1]
        import sys
        for stage,path in enumerate(sorted((root/'lessons').glob('*/code.py')),1):
            if stage < 3: continue
            with self.subTest(lesson=path.parent.name):
                spec=importlib.util.spec_from_file_location('boundary_'+path.parent.name,path)
                m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m
                try:
                    spec.loader.exec_module(m)
                    scope=m.Scope();registry=m.Registry()
                    async def body(args,token):return 42
                    registry.register(scope,m.Tool('double',body))
                    if stage>=4:
                        result=asyncio.run(m.run_batch([call()],registry,scope,m.Session(),m.Policy(decide=lambda _:'ask')))
                        self.assertEqual(result[0]['code'],'DENIED')
                    if stage>=5:
                        self.assertFalse(m.parallel_safe(m.Tool('x',body,parallel=lambda _:'yes'),{}))
                    if stage>=6:
                        session=m.Session();session.append('assistant/message',calls=[call()])
                        with self.assertRaises(ValueError):session.compact_prefix(1,'unsafe cut')
                    if stage>=7:
                        catalog=m.SkillCatalog();catalog.register('x','brief','body');catalog.list();self.assertEqual(catalog.loads,0)
                    if stage>=8:
                        session=m.Session(depth=2);session.append('user/message',text='x')
                        with self.assertRaises(ValueError):session.fork(0,runtime_depth=0,max_depth=2)
                    scope.close();self.assertIsNone(registry.get('double',scope))
                finally:sys.modules.pop(spec.name,None)
    def test_printed_codebook_matches_runnable_snapshots(self):
        import re
        root=Path(__file__).resolve().parents[1]
        book=(root/'docs/13-codebook.md').read_text()
        chunks=re.findall(r'```python\n(.*?)\n```',book,re.S)
        printed='\n'.join(chunks)+'\n'
        expected=''.join((root/'lessons'/name/'code.py').read_text() for name in ['s01_loop','s08_subagents'])
        self.assertEqual(printed,expected)
    def test_all_cumulative_snapshots_run(self):
        root=Path(__file__).resolve().parents[1]
        for path in sorted((root/'lessons').glob('*/code.py')):
            with self.subTest(lesson=path.parent.name):
                spec=importlib.util.spec_from_file_location(path.parent.name,path)
                module=importlib.util.module_from_spec(spec)
                import sys
                sys.modules[spec.name]=module
                try:
                    spec.loader.exec_module(module)
                    result=module.run() if path.parent.name=='s01_loop' else asyncio.run(module.demo())
                    json.dumps(result)
                finally:sys.modules.pop(spec.name,None)

if __name__=='__main__':unittest.main()
