# S07 目录、正文、模型输入是三件事

上一课从已经积累的历史里移走旧细节。另一个更早的节省机会是：根本不要把这次任务不需要的知识提前送进请求。

假设宿主有许多技能，每个技能都有简短描述和较长的操作说明。用户只要求“解释已确认的42”，却把所有技能正文都塞给模型，目录虽然方便，输入也被无关内容挤满。反过来，如果宿主只是调用load('explain')，就以为模型已经学到了正文，模型下一次请求里可能什么也没增加。

本课追踪同一个标记MARKER_EXPLAIN，看它怎样跨过三个不同边界：**发现目录、取出正文、显式注入模型历史。** 不用回答“看起来像懂了”作为证据，直接检查ScriptedModel保存的实际请求。

## 一个标记，三次真实请求

在项目根目录运行：

```sh
python3 walkthroughs/s07_skills.py visibility
```

explain技能只有一段自写说明：MARKER_EXPLAIN: Show the input, operation, and confirmed output. 标记只放在正文，不放在名称和description里。这样，目录中出现explain不能被误认为模型已经看见正文。

脚本的关键输出为：

```json
{
  "catalog": [{"name": "explain", "description": "Explain a verified result"}],
  "body_already_stored": true,
  "load_counts": [0, 1, 1],
  "request_has_marker": [false, false, true],
  "injection_recorded": true,
  "first_request_still_has_marker": false
}
```

完整输出中的actual_requests保存三次请求的消息列表。三个布尔值依次对应“目录已注入”“正文已取出但未注入”“正文已注入”。最后一个false说明第三次注入没有倒过来修改第一次请求的历史快照。

![目录发现、正文获取、显式注入三个边界，以及注册时正文已经保存在内存中的事实](../assets/s07-three-boundaries.svg)

注意图下方的内存框：本课并没有在load时才读文件。正文在register时已经存进字典；延迟发生在**取用与进入上下文**，不是磁盘I/O。这个差别决定了你应该测什么：这里测load次数和实际请求内容，不测磁盘读次数。

## 目录只回答“有哪些可选知识”

先读新增类的前半段：

[本课 code.py：注册与目录发现，第 249–258 行](../lessons/s07_skills/code.py#L249-L258)

<!-- snippet: lessons/s07_skills/code.py:249:258 -->
```python
class SkillCatalog:
    def __init__(self):
        self.skills = {}
        self.loads = 0

    def register(self, name, description, body):
        self.skills[name] = (description, body)

    def list(self):
        return [{"name": name, "description": item[0]} for name, item in sorted(self.skills.items())]
```

skills字典保存name到(description, body)的映射。register没有工具体、没有Session参数，也不发模型请求。它只让宿主能够找到这段知识。同名register在这个简化字典里会覆盖旧项，并没有S03那种作用域、身份token和撤销机制。

list构造一组新字典，每项只拿item[0]，也就是description，不拿item[1]正文。sorted让名称顺序稳定；loads在这一段没有被递增。

读目录也不意味着模型自动看见目录。走读脚本特意把目录序列化后追加到Session，再发第一次请求：

[走读脚本：目录进入第一次请求，第 29–35 行](../walkthroughs/s07_skills.py#L29-L35)

<!-- snippet: walkthroughs/s07_skills.py:29:35 -->
```python
async def visibility_case(skip_injection=False):
    skills, session = catalog(), h.Session()
    session.append('user/message', text='Explain the confirmed result 42.')
    index = skills.list()
    session.append('user/message', text=json.dumps(index, sort_keys=True))
    counts = [skills.loads]
    after_list = await request(session)
```

这里有两个不同动作：skills.list()得到Python列表；session.append把这个列表的JSON文本记成一条可见消息。若省略append，模型连技能名称都看不到。

本例实际第一次请求包含用户任务和这一条目录文本，既没有MARKER_EXPLAIN，也没有body字段。注意description自身也会发送给模型：如果你把整篇正文错误塞进description，list虽然仍叫“目录”，轻量边界已经被你破坏。

目录是否足够短、描述是否能帮助选对技能，是另外的设计与评测问题。名称和描述分离是结构，不会自动带来优秀路由。

## load返回正文，但没有任何隐藏注入

取出正文的全部实现如下：

[本课 code.py：成功取出正文才计数，第 260–263 行](../lessons/s07_skills/code.py#L260-L263)

<!-- snippet: lessons/s07_skills/code.py:260:263 -->
```python
    def load(self, name):
        body = self.skills[name][1]
        self.loads += 1
        return body
```

body从内存字典的第二项读出，loads加1，然后把字符串交还调用者。函数没有拿到Session，没有调用append，也没有接触model。因此仅靠这四行代码，不可能改变下一次请求的messages。

在同一段实验中，第二次请求正好放在load之后、append之前：

[走读脚本：有正文变量，模型仍看不见，第 36–38 行](../walkthroughs/s07_skills.py#L36-L38)

<!-- snippet: walkthroughs/s07_skills.py:36:38 -->
```python
    body = skills.load('explain')
    counts.append(skills.loads)
    after_load = await request(session)
```

此时局部变量body确实含标记，loads也确实变成1。但session没有收到body，after_load仍不含标记。这就是load_counts=[0,1,1]而request_has_marker第二项仍为false的原因。

如果程序员看到loads=1便断言“模型用上了技能”，他检查的是错误的边界。load只能证明宿主成功取出正文；模型输入必须从实际请求里另查。

### 同一正文取两次，会怎样？

```sh
python3 walkthroughs/s07_skills.py retrieval
```

输出为：

```json
{
  "load_counts": [0, 1, 2, 2],
  "same_body": true,
  "missing_skill_error": "KeyError"
}
```

两次成功取正文都加1，所以loads不是“不同技能数”，也不是“缓存未命中数”。第三次查missing时，字典访问先抛KeyError，尚未走到自增语句，因此计数仍为2。

这个顺序也提示错误处理该放在哪里：调用者需要决定找不到技能时怎么提示或改选，不能把一个不存在的正文默默当作已经注入。当前agent_loop没有自动发现、选择或读取技能的分支。

## 真正跨入模型历史的是append

第三步的代码故意保持显式：

[走读脚本：正文注入后再发请求，第 39–44 行](../walkthroughs/s07_skills.py#L39-L44)

<!-- snippet: walkthroughs/s07_skills.py:39:44 -->
```python
    if not skip_injection:
        session.append('user/message', text=body, skill='explain')
    after_injection = await request(session)
    counts.append(skills.loads)
    requests = [after_list, after_load, after_injection]
    seen = [contains_marker(messages) for messages in requests]
```

skill='explain'在本课只是保存在事件data里的来源标签；text才是正文。append给这次知识输入一个日志位置，之后messages()从surface派生下一轮输入。注入既不会执行技能文字，也不创建一个叫explain的Tool。

这条user/message是教学消息格式，用来观察数据流，并不表示“技能文本从此拥有真实用户指令的授权地位”。真实宿主应区分用户输入、知识来源与指令上下文；执行权仍由工具管线判断。

为何说第三次是“实际请求”，而不是脚本自己拼了一份预期列表？因为探针直接调用本课agent_loop：

[走读脚本：从模型记录中取请求，第 22–26 行](../walkthroughs/s07_skills.py#L22-L26)

<!-- snippet: walkthroughs/s07_skills.py:22:26 -->
```python
async def request(session):
    model, scope = h.ScriptedModel([{'text': 'Received.'}]), h.Scope()
    await h.agent_loop(model, h.Registry(), scope, session)
    scope.close()
    return model.requests[0]
```

agent_loop内部先从Session取当前messages，再把它交给respond：

[本课 code.py：模型请求的唯一入口，第 234–240 行](../lessons/s07_skills/code.py#L234-L240)

<!-- snippet: lessons/s07_skills/code.py:234:240 -->
```python
async def agent_loop(script, registry, scope, session, max_steps=4, policy=None):
    """The fake provider receives the derived history on every actual request."""
    model = script if isinstance(script, ScriptedModel) else ScriptedModel(script)
    for step in range(max_steps):
        session.append("step/start", step=step)
        response = model.respond(session.messages())
        session.append("assistant/message", **response)
```

ScriptedModel在返回固定响应前复制收到的输入：

[本课 code.py：留存每次实际请求，第 21–26 行](../lessons/s07_skills/code.py#L21-L26)

<!-- snippet: lessons/s07_skills/code.py:21:26 -->
```python
    def respond(self, messages):
        self.requests.append(snapshot(messages))
        try:
            return snapshot(next(self.responses))
        except StopIteration as exc:
            raise RuntimeError("script ended without a final response") from exc
```

三个位置连起来才构成证据链：append正文 → messages()投影 → respond收到并快照保存。固定响应都是“Received.”，它不读取标记，不会证明模型理解了技能；本实验验证的是正文是否送达请求边界。

第三次请求的末项实际为：

```json
{
  "role": "user",
  "text": "MARKER_EXPLAIN: Show the input, operation, and confirmed output.",
  "skill": "explain"
}
```

S06的压缩仍适用。若未来又把这条技能正文替换成摘要，模型之后能见到什么，应重新从surface和实际请求判断，不能永久把一次load计数当作“当前正文还在上下文里”。

## 故障对照：只漏一行，计数看起来仍正常

不要修改内核，直接跳过正文append：

```sh
python3 walkthroughs/s07_skills.py visibility --skip-injection
```

同一技能仍被成功load，输出却变成：

```json
{
  "body_already_stored": true,
  "load_counts": [0, 1, 1],
  "request_has_marker": [false, false, false],
  "injection_recorded": false
}
```

故障不在字典、不在计数器，也不在模型“忘记了知识”：宿主根本没有把正文送进去。修复就是恢复显式append，再核对actual_requests的末项。

不要为修复它偷偷在load内部修改一个全局Session。那样会让“拿到字符串”和“改变会话”变成不可分的副作用，读同一技能两次可能还会不经意地注入两遍。保持三个步骤独立，才能明确决定是否加载、是否复用、何时注入以及记录什么来源。

## 技能说“已授权”，工具仍须经过Policy

知识文字可能包含操作建议，但不应靠一句话更改执行许可。以下实验故意把正文写成“所有write工具都已获授权”，同时让S04的Policy保持deny。

![技能正文影响模型输入，模型提出write仍会经过Policy，deny产生工具结果而不进入工具体](../assets/s07-knowledge-policy.svg)

走读中的写工具只会向内存列表entered追加一项；不会操作真实文件。我们用固定模型明确提出w1调用，避免把是否提出调用与是否允许执行混在一起：

[走读脚本：用真实调用链验证权限不变，第 84–96 行](../walkthroughs/s07_skills.py#L84-L96)

<!-- snippet: walkthroughs/s07_skills.py:84:96 -->
```python
    async def write(args, token):
        entered.append('write')
        return 'changed'

    registry.register(scope, h.Tool('write', write))
    calls = [{'id': 'w1', 'name': 'write', 'args': {}}]
    model = h.ScriptedModel([{'calls': calls}, {'text': 'Write was denied.'}])
    await h.agent_loop(model, registry, scope, session,
                       policy=h.Policy(decide=lambda _: 'deny'))
    results = [e['data'] for e in session.events if e['type'] == 'tool/result']
    report = {'skill_in_request': contains_marker(model.requests[0]),
              'body_entries': entered, 'result': results[0],
              'next_request_result': model.requests[1][-1]}
```

```sh
python3 walkthroughs/s07_skills.py policy
```

实际结果：

```json
{
  "skill_in_request": true,
  "body_entries": [],
  "result": {"call_id": "w1", "ok": false, "code": "DENIED"},
  "next_request_result": {"role": "tool", "call_id": "w1", "ok": false, "code": "DENIED"}
}
```

标记证明正文已经进入模型请求；body_entries为空证明工具体没有进入；下一次请求收到DENIED证明拒绝也沿正常结果通路反馈给模型。三个观测对象不能互相替代。

本实验不是说任意技能都安全，也没有验证模型抗提示注入能力。它只证明当前执行链不从技能字符串中自动生成许可。来自外部的知识、相对资源或可执行脚本，仍需要各自的信任与授权边界。

## 练习：沿输入链定位缺口

先猜结果，再运行；每项都无需修改教学内核：

| 练习 | 命令或修改点 | 观测标准 |
|---|---|---|
| 找到遗漏注入 | python3 walkthroughs/s07_skills.py visibility --skip-injection | loads仍到1，但三次请求均无标记 |
| 恢复注入 | python3 walkthroughs/s07_skills.py visibility | 请求标记false、false、true，旧请求仍无标记 |
| 重复读取同一正文 | python3 walkthroughs/s07_skills.py retrieval | 两次成功load得到同一正文，计数到2；missing不再增加 |
| 把知识与许可分开 | python3 walkthroughs/s07_skills.py policy | 正文可见，body_entries仍为空，结果DENIED |

扩展练习：在catalog()里再注册一个只用于写诗的技能，把独有标记MARKER_POEM放在它的body中，不改explain的描述。list应出现两个名称，但三次explain请求都不应含MARKER_POEM。检查实际请求而不是只检查catalog.loads，可以证明无关正文没有提前进入上下文。最后恢复原脚本，运行全部固定实验：

```sh
python3 walkthroughs/s07_skills.py all
```

[完整观测输出](../walkthroughs/expected/s07_skills.json)保留每次实际请求。异步入口用5秒wait_for限制后来加入的协作等待；原实验不发网络请求，也没有真实模型推理。它不是强制中断同步死循环的沙箱。

## 对照DeepSeek：知识接口与输入接口仍要分开看

[SkillSummary、SkillCandidate与SkillDefinition](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/skill/skill/src/index.ts#L57-L106)分别表达目录摘要、提供方候选和含content的完整定义。先找description与content在哪种类型出现，再看rank、provider和locator为何属于另一个层面。它们是来源与解析问题，不是工具执行许可。

[显式技能调用来源与正文渲染](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/skill/skill/src/index.ts#L139-L183)把skill-invocation来源和正文的模型可见结构单独定义出来。这个范围展示的是来源类型与render函数，不是完整的调用调度。不要从“存在渲染函数”跳到“目录自动注入了全部正文”。

本课只用一个内存字典和显式消息注入说明边界，没有实现提供方合并、资源解析、作用域优先级、调用策略或真实文件懒加载。也没有计算token节省、缓存命中或费用。

现在能把适量知识放进一条会话了。如果解释任务想交给另一个工作单元，应该共享父会话列表，还是复制一个可追溯的事实前缀？下一课从同一个已确认结果42出发，让子会话获得上下文，但不能悄悄改写父级状态。
