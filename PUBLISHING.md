# 构建与 GitHub Pages

## 本地阅读

Python 3.10+运行教学实验；安装Pandoc后运行 `make check`，得到site/。网站使用相对资源与原生HTML，可直接打开site/index.html，也可运行 `python3 -m http.server 8000 --directory site`。

讲义以docs/中的Markdown为内容源，修改正文不需要编辑网页。普通build读取当前code.py与Markdown，既不重生成课程快照，也不重写练习。若片段或预期输出与改动不一致，检查会报告错误供你判断。只有明确执行 `make regenerate`才覆盖累计快照、差异、代码册与记录轨迹。

## 官方 Pages 工作流

[pages.yml](.github/workflows/pages.yml)使用固定commit的官方GitHub Actions，版本与审查来源记录在[actions-lock.json](.github/actions-lock.json)。流水线安装Ubuntu官方仓库的Pandoc，执行Python测试、来源及片段检查、静态构建、链接检查和真实走读输出比对，再上传site/。

1. 在仓库的Settings → Pages → Build and deployment中选择GitHub Actions。
2. main分支推送会检查并部署；Pull Request只检查，不部署。
3. 部署任务使用GitHub提供的临时身份与最小pages/id-token权限，不需要仓库secret、部署密钥或模型凭据。
4. 若默认分支不是main，请同时修改工作流的push分支过滤。部署条件仍检查默认分支，防止普通分支被发布。

工作流不依赖Chromium、GPU、模型服务或PDF。site/、output/、dist/不提交；Pages部署从每次检查通过的静态产物取得内容。

## 项目子路径与离线资源

所有内部HTML、Markdown、代码和图链接均为相对路径。代码定位在本地生成的code.py.html#L行号，原始code.py仍可下载。来源引用指向固定DeepSeek commit，只有点击这些外部源码链接才需要联网。样式、字体选择、搜索数据、轨迹回放都不依赖CDN。

静态链接检查同时按域名根路径和 `/learn-deepseek-harness/` 项目子路径解析链接。更换仓库名不需要修改资源前缀。

## 可选 PDF

网页与Markdown是维护入口。个人需要阅读副本时，可打印site/book.html，或在本地可信Chromium环境运行 `make pdf`。PDF不进入默认构建与Pages下载区，内容变化后需要重新导出。

## 更新来源时

先审阅新的上游commit及契约，逐个更新sources.json中的锚点、文件哈希、对应教学解释与实验，不要只替换版本字符串。sources.json与离线reference/upstream必须一致；必要的上游MIT许可始终保留。
