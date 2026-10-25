# 轨迹实验室

这不是实时模型，也不会在浏览器执行 Python。下面的逐步回放来自 scripts/build_traces.py 实际运行本项目教学代码生成的固定轨迹。改变代码后重新生成，才会改变轨迹。每个事件同时展示日志事实和模型可见消息。

<div class="trace-lab" data-trace-lab>
<label for="trace-case">选择实验</label><select id="trace-case" aria-label="选择实验"></select>
<div class="trace-controls"><button id="trace-prev">上一步</button><button id="trace-next">下一步</button><button id="trace-reset">重置</button><span id="trace-position" aria-live="polite"></span></div>
<div class="trace-grid"><section><h3>已提交的事件</h3><pre id="trace-event"></pre></section><section><h3>此时模型可见的历史</h3><pre id="trace-projection"></pre></section></div>
<p id="trace-observation" aria-live="polite"></p>
</div>

## 怎样观察

先预测，再点下一步。tool/call 出现时，能否认定工具已经成功？不能。遇到 step/start，模型消息数量会增加吗？不会。surface/replace 之后，为什么日志条数增加，可见消息反而减少？因为原事实保留，投影变了。

以下为同一批轨迹的打印版。关闭 JavaScript 仍可阅读，PDF 不丢失核心观察。

## 允许后执行并回灌

| seq | 事件 | 可见消息数 | 关键事实 |
|---|---|---|---|
| 0 | user/message | 1 |  |
| 1 | step/start | 1 |  |
| 2 | assistant/message | 2 | 请求 c1 |
| 3 | tool/call | 2 | 记录调用，不代表成功 |
| 4 | tool/result | 3 | 42 |
| 5 | step/end | 3 |  |
| 6 | step/start | 3 |  |
| 7 | assistant/message | 4 |  |
| 8 | step/end | 4 |  |

## 没有审批通道时拒绝

| seq | 事件 | 可见消息数 | 关键事实 |
|---|---|---|---|
| 0 | user/message | 1 |  |
| 1 | step/start | 1 |  |
| 2 | assistant/message | 2 | 请求 c1 |
| 3 | tool/call | 2 | 记录调用，不代表成功 |
| 4 | tool/result | 3 | DENIED |
| 5 | step/end | 3 |  |
| 6 | step/start | 3 |  |
| 7 | assistant/message | 4 |  |
| 8 | step/end | 4 |  |

## 取消后保留完整结算

| seq | 事件 | 可见消息数 | 关键事实 |
|---|---|---|---|
| 0 | user/message | 1 |  |
| 1 | step/start | 1 |  |
| 2 | assistant/message | 2 | 请求 c1 |
| 3 | tool/call | 2 | 记录调用，不代表成功 |
| 4 | tool/result | 3 | ABORTED |
| 5 | step/end | 3 |  |
| 6 | step/start | 3 |  |
| 7 | assistant/message | 4 |  |
| 8 | step/end | 4 |  |

## 重放区分未开始与结果未知

| seq | 事件 | 可见消息数 | 关键事实 |
|---|---|---|---|
| 0 | user/message | 1 |  |
| 1 | assistant/message | 2 | 请求 a,b |
| 2 | tool/call | 2 | 记录调用，不代表成功 |
| 3 | tool/result | 3 | TOOL_OUTCOME_UNKNOWN |
| 4 | tool/result | 4 | TOOL_NOT_STARTED |

## 替换可见面而保留原日志

| seq | 事件 | 可见消息数 | 关键事实 |
|---|---|---|---|
| 0 | user/message | 1 |  |
| 1 | assistant/message | 2 | 请求 c1 |
| 2 | tool/call | 2 | 记录调用，不代表成功 |
| 3 | tool/result | 3 | 42 |
| 4 | assistant/message | 4 |  |
| 5 | surface/replace | 2 | 原日志保留；可见面被替换 |

## 故障挑战

把恢复逻辑中的 UNKNOWN 错写为 NOT_STARTED，再运行对应测试。测试应失败，而不是修改预期值迎合实现。再把结果按完成顺序提交，运行有序结算测试，解释为什么看似更快的展示可能破坏稳定历史。

教学轨迹没有计入真实网络延迟、token 数、GPU 时间或生产吞吐率。不要把事件序号解释成毫秒，也不要从这里推断上游性能。
