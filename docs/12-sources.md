# 来源许可与可重现构建

## 固定源码，让解释可以核查

本教程依据 [DeepSeek Harness 固定提交](https://github.com/deepseek-ai/deepseek-harness/tree/22ddee3792402c3e70ec5f86a63c3e3e895a2f60)。[upstream.lock.json](../upstream.lock.json)记录版本，[sources.json](../sources.json)列出文件、完整commit、行范围、定位符和SHA-256。reference/upstream保留引用到的MIT源文件，供离线核对；它们不参与Python实验，也不是运行依赖。

固定版本不等于追踪了上游未来的修复。更新时应先比较契约与测试变化，再审查实验和讲义；不能只换URL里的SHA，却保留旧行号与旧解释。

## 许可

- 课程讲义、机制图、Python教学代码与阅读界面采用 [MIT许可](../LICENSE)。
- 附带DeepSeek Harness源码的版权与MIT条款保留于 [上游许可](../legal/DeepSeek-Harness-MIT.txt)。
- 本项目是独立教学项目，不是DeepSeek官方教程，不代表上游背书。

上游固定提交的 [SAFETY.md](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/SAFETY.md#L1-L27)说明其开发预览与安全边界。教学中的Policy、guard和Scope并不提供操作系统隔离。

## 内容与代码放在哪里？

```text
book.json                  课程顺序与页面元数据
sources.json               固定源码锚点及文件哈希
docs/                      直接可读、可编辑的Markdown讲义
lessons/s01...s08/code.py   各课累计的独立运行代码
lessons/*/delta.patch       相邻阶段差异
walkthroughs/              正文所用的可执行走读与故障反例
walkthroughs/expected/     从实际运行保存的观察结果
examples/                  共用教学组件与综合实验
tests/                     机制边界测试
assets/                    SVG、CSS与离线交互脚本
reference/upstream/        供离线核验的MIT参考源码
site/                      生成的网站，不提交
output/                    可选本地阅读导出，不提交
```

## 日常构建不覆盖练习

运行实验只需要Python 3.10或更新版本。网页转换使用 [Pandoc](https://pandoc.org/installing.html)。默认流程不下载模型、不需要密钥、不启动Chromium，也不携带旧PDF。

```sh
make test
make validate
python3 scripts/check_walkthroughs.py
make build
```

`make build`读取已提交的Markdown和每课code.py，生成静态HTML。正文中的片段若与代码不一致，检查会失败并报告具体文件和行号，**不会悄悄重写你刚做的练习**。修改后的行为若改变了走读结果，应解释差异、检查预期是否合理，而不是直接把测试改绿。

每个网页都有Markdown、完整代码、相邻差异入口；代码链接定位到真实行号，图可横向滚动或打开原图。资源使用相对路径，因此可离线打开，也可部署在GitHub Pages项目子路径。搜索、主题和学习进度不需要服务端。

### 维护者的显式再生成

只有明确维护累计快照时才运行：

```sh
make regenerate
```

该命令会从examples中的组件生成课程快照、delta.patch、代码册，并从实际内存实验重新记录轨迹讲义与回放数据。它**会覆盖这些目标文件**，因此应先保存自己的练习，再审查差异。日常build和Pages CI不会调用它。走读expected JSON也不会被普通检查自动更新。

如果需要恢复离线参考源码，可对已审查的同一固定checkout运行 `python3 scripts/lock_sources.py --from-checkout /path/to/deepseek-harness`。脚本先核对commit与文件哈希，不执行上游代码；它不会替你选择新版本或新锚点。

### 可选阅读副本

Markdown与网页是课程的维护入口。若需要临时纸面阅读，可在本地打开 `site/book.html` 打印，或运行 `make pdf`，使用已安装的可信Chromium。PDF位于output/pdf，不进入默认仓库或网站；修改内容后需要自行重新导出。浏览器与中文字形支持取决于本地环境，不是课程测试前提。

## 固定源码地图

下表与sources.json对应。每个链接都指向完整commit，而不是浮动主分支。

| 机制 | 固定源码锚点 |
|---|---|
| 总体架构与事件域 | [docs/architecture.zh.md L7–L173](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/docs/architecture.zh.md#L7-L173) |
| ReactLoopAgent 的步骤驱动 | [packages/core/agent-loop/src/agent.ts L428–L617](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/agent-loop/src/agent.ts#L428-L617) |
| 请求准备与日志提交 | [packages/core/agent-loop/src/agent.ts L606–L725](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/agent-loop/src/agent.ts#L606-L725) |
| 默认驱动器的公开约定 | [packages/core/agent-loop/README.md L73–L84](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/agent-loop/README.md#L73-L84) |
| Session 及消息投影 | [packages/core/session/src/index.ts L999–L1024](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/session/src/index.ts#L999-L1024) |
| 未开始与结果未知的恢复分类 | [packages/core/session/src/repair.ts L15–L196](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/session/src/repair.ts#L15-L196) |
| 作用域的继承与生命周期 | [packages/core/scope/src/index.ts L137–L171](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/scope/src/index.ts#L137-L171) |
| 工具注册表与单调守卫 | [packages/core/tools/src/index.ts L99–L218](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/tools/src/index.ts#L99-L218) |
| 工具准备阶段的审批和守卫 | [packages/core/tools/src/pipeline.ts L190–L237](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/tools/src/pipeline.ts#L190-L237) |
| 无审批通道时拒绝执行 | [packages/core/tools/src/pipeline.ts L436–L474](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/tools/src/pipeline.ts#L436-L474) |
| 并发池与独占屏障 | [packages/core/tools/src/batch.ts L50–L279](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/tools/src/batch.ts#L50-L279) |
| 并发属性必须显式为 true | [packages/core/tools/tests/execution-mode.spec.ts L26–L130](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/tools/tests/execution-mode.spec.ts#L26-L130) |
| 压缩边界的工具配对检查 | [packages/compaction/compaction/src/tool-pairing.ts L29–L83](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/compaction/compaction/src/tool-pairing.ts#L29-L83) |
| CompactionEngine 的替换契约 | [packages/compaction/compaction/src/index.ts L119–L195](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/compaction/compaction/src/index.ts#L119-L195) |
| 技能目录与按需正文 | [packages/skill/skill/src/index.ts L57–L106](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/skill/skill/src/index.ts#L57-L106) |
| 持久化委派深度不回退 | [packages/subagent/subagent/src/depth.ts L28–L39](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/subagent/subagent/src/depth.ts#L28-L39) |
| 按事件前缀构造子会话 | [packages/core/session/src/fork.ts L21–L30](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/session/src/fork.ts#L21-L30) |
| Profile 与分层组合 | [docs/architecture.zh.md L13–L37](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/docs/architecture.zh.md#L13-L37) |
| Cordis 的可逆副作用与分发语义 | [docs/cordis-primer.zh.md L7–L51](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/docs/cordis-primer.zh.md#L7-L51) |
| 开发预览安全边界 | [SAFETY.md L1–L27](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/SAFETY.md#L1-L27) |
| 成功结果最终物化前的取消检查 | [packages/core/tools/src/pipeline.ts L336–L359](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/core/tools/src/pipeline.ts#L336-L359) |
| 技能正文渲染与持久来源 | [packages/skill/skill/src/index.ts L139–L183](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/skill/skill/src/index.ts#L139-L183) |
| 子级深度递增与绝对上限 | [packages/subagent/subagent/src/child-agent.ts L49–L58](https://github.com/deepseek-ai/deepseek-harness/blob/22ddee3792402c3e70ec5f86a63c3e3e895a2f60/packages/subagent/subagent/src/child-agent.ts#L49-L58) |

## 验证能证明什么？

教学测试检验纯内存状态、事件顺序、错误分支、作用域归属、压缩配对与委派深度；源码检查检验固定文件的字节和行定位；片段检查检验正文中的Python与课件代码逐字一致。这三种证据各有用途，不能相互替代。

这些检查没有运行官方dsh、真实模型、文件或网络工具，没有检验宿主沙箱、持久化迁移、完整插件生态或生产可靠性。异步走读的有界等待也不是对恶意同步代码的强制隔离。
