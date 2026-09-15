# Codex Team

Codex Team 可以让一个主 Codex 把工作分给多个 Coding Agent，例如其他 Codex 账号、Kimi、通义、DeepSeek 和智谱 GLM。你只要在项目对话中说清楚想要什么，主 Codex 会安排分工、汇总结果并检查项目。

它在你的 Mac 本机运行。项目文件、账号登录和 API Key 不会上传到 Codex Team 自己的网站。

## 第一次使用：只做 3 步

### 1. 安装并打开

在 Finder 中打开 Codex Team 文件夹，双击：

**`setup.command`**

它会自动安装 Codex Team Skill，并打开本地设置页面。第一次双击时，macOS 如果阻止打开，请右键这个文件，选择“打开”。

如果提示缺少 Codex，请先安装并打开 Codex，登录你的主账号，再重新双击 `setup.command`。

### 2. 选择协作团队

打开的页面地址应以 `http://127.0.0.1` 开头。按下面做：

1. 在“主账号”中选择负责分工和检查结果的 Codex。
2. 在“参与工作的 Agent”中勾选要使用的账号或模型。
3. 点击“保存，以后直接使用”。

页面中没有你想用的 Agent 时，在右侧选择类型并添加：

- **Codex**：添加账号名称，然后按页面提示登录。
- **Kimi 账号登录**：适合已经安装 Kimi Code、按账号套餐使用的人。
- **Kimi API、通义、DeepSeek、智谱**：填写名称、模型和 API Key。

API Key 会保存在这台 Mac 的系统钥匙串中，不会写进项目文件。

### 3. 在项目对话中交代任务

在 Codex 中打开你真正要处理的项目，然后输入：

```text
$codex-team 请多个 Agent 一起完成：制作登录页面，并检查现有功能有没有问题
```

把冒号后面的文字换成你的要求即可。项目目标、项目目录和分工不需要在设置页面重复填写。

## 以后怎么用

平时不需要一直打开 Codex Team 网页，也不用每次重新选择账号。只需：

1. 在 Codex 中打开目标项目。
2. 在项目对话中输入 `$codex-team` 和你的要求。
3. 等待主 Codex 汇总并检查结果。

想更换账号、模型、并行数量或成本策略时，再双击 `start.command` 修改设置并保存。

你也可以直接说“让多个 Agent 一起做这个项目”。Skill 允许自动识别这类请求；写出 `$codex-team` 最稳妥。

## 它会做什么

- 主 Codex 先判断任务是否需要拆分，不会为了凑数量而强行分工。
- 每个 Agent 在单独的临时工作区中工作，避免同时改坏同一份文件。
- 主 Codex 汇总各 Agent 的修改，并做最终检查。
- 主账号可以参与执行，但默认优先使用其他已选择的 Agent，避免把任务全分给自己。
- 页面会按项目和模型统计运行次数、Token 和可估算的 API 费用。读取统计本身不消耗 Token。

## 常见问题

### 项目一定要上传到 GitHub 吗？

不需要。没有 Git 的普通文件夹也能用，Codex Team 会在本机建立版本记录。这不会创建 GitHub 仓库，也不会上传文件。

### 为什么需要本地版本记录？

多个 Agent 会同时修改文件。本地版本记录让每个 Agent 分开工作，再安全地汇总修改。它只是本机的“后悔药”，和是否公开到 GitHub 是两回事。

### Kimi 一定要 API Key 吗？

不一定。Kimi 有两种 Agent：

- “Kimi 账号登录”使用 Kimi Code 的登录状态，不填写 API Key。
- “Kimi 开放平台 API”按 API 用量计费，需要 API Key。

两种方式可以同时添加，作为两个不同的 Agent 使用。

### DeepSeek、通义和智谱为什么显示在线却不能执行？

“在线”只表示本机已经保存了配置。真正执行还需要正确的 API Key、模型名称、可用额度和网络连接。失败时请查看最近任务中的具体原因。

### 需要一直开着设置网页吗？

不需要。网页只用于添加 Agent、调整团队和查看统计。通过 `$codex-team` 开始任务时会直接读取上次保存的设置。

### 可以在另一台 Mac 使用吗？

可以。把完整项目从 GitHub 下载到另一台 Mac，再双击 `setup.command`。为了保护账号，每台 Mac 都需要分别登录 Codex/Kimi，并重新填写 API Key。

iPhone 和 iPad 可以查看 GitHub 上的代码，但不能直接运行依赖 Mac 本地程序的 Codex Team。若希望手机发起任务，需要让一台 Mac 保持在线，并另外增加远程任务入口。

### 可以只在 Codex 里从 GitHub 安装这个 Skill 吗？

Codex 可以从 GitHub 安装普通 Skill，但 Codex Team 还包含本地设置页面、账号隔离和调度程序。只安装 `skill/codex-team` 文件夹会缺少这些程序。

因此当前推荐安装完整 Codex Team 文件夹，再双击 `setup.command`。安装完成后，日常使用就和普通 Skill 一样，直接在 Codex 对话中输入 `$codex-team`。

未来可以把完整程序封装为 Codex 插件或安装包，做到从插件页面一次安装；调度程序仍需要运行在能访问项目和各家 CLI 的电脑上。

## 更新和 GitHub 同步

双击 `github-sync.command` 可以把程序代码同步到 GitHub。第一次会帮助创建仓库；以后会上传本地更新并下载其他电脑上的更新。

账号登录、API Key、团队设置、项目记录和运行日志不会上传。仓库是否公开由 GitHub 的可见性设置决定；公开仓库时，任何人都能看到程序代码，但仍看不到被排除的本地凭据。

不要直接双击 `web/index.html`。那只是一份网页文件，无法读取本机账号。请使用 `setup.command` 或 `start.command`，正确地址会以 `http://127.0.0.1` 开头。

## 给熟悉技术的用户

运行环境为 macOS/Linux、Python 3.9+、Git 和 Codex CLI。Kimi Agent 需要 Kimi Code；Kimi API、通义、DeepSeek 和智谱 Agent 通过 Qwen Code 的 OpenAI 兼容方式运行。

配置和运行数据默认位于 `codex-team-state`。Codex 账号使用独立 `CODEX_HOME`，Kimi 账号使用独立 `KIMI_CODE_HOME`，API Key 在 macOS 钥匙串的 `CodexTeam-Agent-Key` 服务中保存。

命令行运行方式：

```bash
python3 codex_team.py --state ./codex-team-state run team.json
```

每个任务会创建 Git worktree。主账号负责自动规划和验收；调度器负责进程、隔离、超时、结果收集和合并。运行结果保存在 `codex-team-state/runs/<运行编号>/`，包括计划、状态、日志、检查结果和集成工作区。

项目若没有配置验收命令，最终状态为 `needs_validation`；配置的检查全部通过时为 `checks_passed`。集成结果不会自动推送、公开或部署。

相关资料：

- [Codex 认证与凭据存储](https://developers.openai.com/codex/auth)
- [Codex 非交互执行](https://developers.openai.com/codex/noninteractive)
- [Codex 高级配置](https://developers.openai.com/codex/config-advanced)
- [Kimi Code](https://github.com/MoonshotAI/kimi-code)
- [Qwen Code Provider 配置](https://github.com/QwenLM/qwen-code/blob/main/docs/users/configuration/auth.md)

只添加你拥有或获准使用的账号，并遵守各账号所属组织的规则。
