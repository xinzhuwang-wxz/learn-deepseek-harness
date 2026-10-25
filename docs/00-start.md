# 从 39 行循环开始搭建 Harness

这是一门独立的教学实践课。你将从一个能运行的模型与工具循环出发，每次增加一个机制，最终得到可回放、可卸载、能拒绝危险动作、能处理取消和子任务的最小 Harness。课程针对 DeepSeek Harness 的实际架构，但不把生产代码压缩粘贴，也不声称教学模型等价于官方实现。

先运行，再预测，再改坏，最后修复。源码链接放在每课末尾：先形成自己的实现，再回到真实代码验证边界。你不必先读完一个大型 monorepo。

## 三分钟起步

需要 Python 3.10 或更新版本。实验仅使用标准库，无 API key、网络请求、模型下载、GPU、shell 工具或主机文件读写工具。教程的构建脚本会读取和写入本项目；这与实验内的 agent 工具是两回事。

```sh
cd learn-deepseek-harness
python3 lessons/s01_loop/code.py
python3 lessons/s04_guards/code.py
python3 -m unittest discover -s tests -v
```

第一个实验应返回一条数值为 42 的工具结果，并以助手文本 42 结束。第二个实验故意没有审批通道，应返回 DENIED，而不是执行工具。若这两件事都发生了，你已经看到了整门课最重要的两个边界：工具结果回到模型；执行权不属于模型本身。

运行 make build 后直接打开 site/index.html，搜索、主题和进度不依赖服务器。网页从 docs/ 下的 Markdown 构建；也可以直接在代码仓库阅读和修改讲义。完整源码包还包含每阶段 code.py、相邻阶段 delta.patch、测试、固定版本源码映射和离线参考文件。

## 逐步长出来的系统

![八个阶段依次加入循环、事件、插件、守卫、结算、压缩、技能与子任务](../assets/evolution.svg)

| 阶段 | 新增的一个核心机制 | 最先观察的失败 | 运行入口 |
|---|---|---|---|
| S01 | 模型与工具闭环 | 下一请求看不到工具结果 | lessons/s01_loop/code.py |
| S02 | 事件日志与投影 | UI 消息不是完整事实 | lessons/s02_events/code.py |
| S03 | 有所有者的插件注册 | 卸载后工具还留着 | lessons/s03_plugins/code.py |
| S04 | 执行前决策管线 | ask 被当成默认允许 | lessons/s04_guards/code.py |
| S05 | 有序结算 | 完成顺序污染模型历史 | lessons/s05_settlement/code.py |
| S06 | 保持协议的上下文压缩 | 截断了调用与结果 | lessons/s06_compaction/code.py |
| S07 | 按需知识加载 | 未使用技能占满上下文 | lessons/s07_skills/code.py |
| S08 | 有边界的子会话 | 共享状态和深度重置 | lessons/s08_subagents/code.py |

每个 code.py 是可单独运行的累计快照，不需要下载上游，不依赖前一课的 Python import。相邻阶段有 diff；各课保留前面已有机制。为了让读者能完整看懂系统，前几课只保留必要抽象，后面才补齐边界。examples/harness.py 是这些原创教学积木的维护源，scripts/build_lessons.py 生成可读快照。

## 怎么安排学习

- 90 分钟速通：S01、S02、S04、S05，重点看闭环、事实和执行边界。
- 半天动手：按 S01 至 S08 顺序运行、做故障注入，再完成综合实验。
- 深入源码：每课完成后读固定 commit 的两个核心锚点，解释教学版省略了什么。

这不是学习时长保证。理解异步执行和状态机的读者可能更快；刚接触 Python 的读者先掌握字典、函数、异常和 async/await。

## 真实项目与教学模型之间

基线固定为 deepseek-ai/deepseek-harness 的 22ddee3792402c3e70ec5f86a63c3e3e895a2f60，核验日期 2026-10-25。真实项目使用 TypeScript、Cordis 和大量可替换服务；本课用 Python 标准库演示因果关系，不兼容 dsh 的配置、事件 schema、插件接口或持久化格式。

上游明确是 developer preview，未通过安全审计。审批、guard 或 sandbox 名称都不构成生产安全保证。我们未安装或运行官方 Harness，没有验证真实模型 API、操作系统沙箱、浏览器、桌面端或远程插件集成。本课程通过的测试只约束教学代码。

[开发预览安全边界](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/SAFETY.md#L1-L27)
