# Codex Team：Codex 主账号与混合 Agent 协作

Python 3.9+，macOS/Linux，Git 和已安装的 Codex CLI。主账号负责检查仓库、自动拆分任务、根据厂商和模型能力选择执行 Agent，并完成最终验收；调度器只负责启动进程、隔离工作区、收集结果和合并。执行 Agent 可以混用多个 Codex 账号、Kimi Code、阿里通义、DeepSeek 和智谱 GLM。每个任务都在独立 Git worktree 中完成，最后由主 Codex 集成和检查。

## 图形界面（推荐）

在 macOS 上双击 `start.command`，浏览器会打开本地控制台。先添加并登录 Agent，再选择主账号、执行 Agent、最大并行数、模型路由策略和单个 Agent 时间上限，点击“保存协作配置”。默认上限为 2 小时；包含大量资料解析或 OCR 的任务可选 4 小时，Agent 完成后会立即结束。主账号必须是 Codex，也可以同时加入执行 Agent 池；执行 Agent 可以混用 Codex、Kimi 和其他已配置模型。规划、并行执行和最终验收按阶段依次运行，同一 Agent 在一轮执行中最多承担一个任务。项目和目标不在控制台重复填写，而是在目标项目的 Codex 对话中通过 `$codex-team` 交给主账号。

路由策略提供“成本优先、均衡、质量优先”三种简单选择。成本优先遵循 cheapest capable model：边界清晰的检索、局部实现、测试和文档优先交给低成本 Agent，复杂架构、跨模块推理和高风险修改保留给强模型；主账号不会为了用满并行数而强行拆分任务。路由只是决策提示，实际节省必须以真实 usage、测试结果和后续 Benchmark 为准。

控制台不保存固定项目，但每次运行会自动记录主账号传入的项目路径、任务名称、状态和日志。“本地统计”面板按项目和模型显示运行状态、输入/缓存/输出 Token 与 API 费用估算。Codex、Kimi 账号及 Coding Plan 等订阅型 Agent 显示“套餐内”，不虚构单次价格；CLI 未返回 usage 时显示“暂无 Token 数据”。Kimi API 和 DeepSeek 根据内置官方价格表估算，其中 DeepSeek 峰谷价格显示为区间。价格表带更新时间，实际账单仍以厂商为准。统计只读取本地 JSON，不调用模型、不消耗 Token。调度器不读取或理解项目业务内容，只在执行时使用路径创建隔离工作区。

控制台只监听 `127.0.0.1`，账号凭据和项目不会上传到一个额外的网站。关闭启动它的终端窗口即可停止控制台。由于它需要调用本机 Git、Codex 和项目文件，因此不提供公网部署版本。

## 多设备使用

GitHub 用于同步程序代码和文档，不会把仓库绑定到某一台电脑。另一台 Mac 可以使用自己的 GitHub SSH Key 或 `gh auth login` 克隆同一个仓库，然后在本机运行 `install-skill.command` 和 `start.command`。

账号登录、API Key、执行池配置、运行日志与项目统计默认不上传 GitHub。每台 Mac 需要分别登录 Codex/Kimi、配置外部模型 Key 并保存协作配置；这是为了避免凭据和本地项目记录进入仓库。iPad 和 iPhone 可以通过 GitHub App、网页或 Codespaces 查看代码、Issue 和提交，但不能直接运行依赖本地 Git 与各模型 CLI 的调度器。若需要从移动设备发起任务，可以后续增加 GitHub Issue 任务队列，由一台保持在线的 Mac 领取执行。

不要直接打开 `web/index.html`。直接打开时地址以 `file://` 开头，本地服务没有启动，页面无法读取账号和项目；新版页面会显示启动提示。正确打开后的地址是 `http://127.0.0.1:8765/`。

控制台会自动读取当前 Codex CLI 登录并显示为“当前 Codex”，也会读取 Codex App 保存的本地项目。多账号协作依赖 Git worktree；已有 Git 项目可以直接启动，非 Git 项目需要先在界面中完成一次本地初始化。

非 Git 项目也可以直接选择。选择后点击“初始化本地 Git”，控制台会在该项目中运行本地初始化、添加当前文件并创建一条初始提交。此操作不会创建远程仓库，也不会上传或推送文件。初始化成功后即可启动多账号协作。

如果当前登录缓存包含 ChatGPT 身份信息，控制台会直接显示账号邮箱、姓名和套餐；这些字段只在本机解析。Codex 默认登录缓存只保留当前账号，无法恢复已经被后续登录覆盖的历史账号。其他 Codex 账号与 Kimi Agent 需要在控制台中分别登录一次，之后使用独立状态目录。浏览器里曾经登录过的 ChatGPT 账号不会被读取。

## 在主账号对话中直接调用

双击 `install-skill.command` 安装本地 Skill。先在 Web 控制台选择一次主账号、执行 Agent、并行数和路由策略，然后点击“保存协作配置”。之后在目标项目的 Codex 对话中直接输入：

```text
$codex-team 使用已配置的 Agent 一起完成登录模块，并运行现有测试
```

Skill 会从当前对话取得目标、从当前工作目录取得项目路径，并让主账号完成拆分和 Agent 分配，然后把执行计划交给本地调度流程并等待结果。项目没有 Git 时，它会先创建本地初始提交；不会创建远程仓库、推送或自动合并回当前分支。

`$codex-team` 是本地 Skill 的直接入口。`@` 用于 App/连接器；若要显示成 `@Codex Team`，需要再封装一个本地 MCP 服务和 Codex 插件。当前调度核心已把 Agent 调用集中在适配器层，后续可以在不改规划与 Git 集成流程的前提下增加更多 CLI 模型。

## Kimi Code

当前电脑未安装 Kimi Code CLI 时，界面会将 Kimi 标为“未安装”。按 Kimi 官方方式安装后重启控制台：

```bash
curl -fsSL https://code.kimi.com/kimi-code/install.sh | bash
```

然后选择“Kimi 账号登录”、填写 Agent 别名并点击 `+`，控制台会运行 `kimi login`。每个 Kimi Agent 使用独立 `KIMI_CODE_HOME`。执行时调用 `kimi -p`，可在 `worker_agents` 条目中增加 `model` 指定模型。

也可以选择“Kimi 开放平台 API”，填写独立别名、模型和从 Kimi 开放平台创建的 API Key。该模式使用 `https://api.moonshot.cn/v1`，通过 Qwen Code 的 OpenAI 兼容接口执行并按 API 用量计费。Key 保存在 macOS 钥匙串，不写入项目或配置文件；账号登录 Agent 与 API Agent 可以同时加入执行池。

## 阿里通义、DeepSeek 与智谱 GLM

这三类 Agent 统一使用 Qwen Code CLI。安装 Qwen Code 后，后续认证可以直接在 Codex Team 前端完成，不必再进入 `qwen /auth`。

重启控制台后，在 Agent 类型中选择“阿里通义”“DeepSeek”或“智谱 GLM”，填写账号名称、模型名称和对应厂商的 API Key，然后点击 `+`。默认模型分别为 `qwen3-coder-plus`、`deepseek-v4-pro` 和 `glm-5`，可在界面覆盖。执行器使用 `qwen -p`、OpenAI 兼容接口和 JSON 输出。无人值守任务采用 Qwen Code 的全自动审批。从 Codex 对话调用时沿用外层 Codex 沙箱；从普通终端独立运行时启用 Qwen 沙箱，在 macOS 上使用内置 Seatbelt。任务文件始终写入独立 Git worktree，外层还有运行超时、Agent 锁和 Git 提交检查。若 Qwen Code 返回权限拒绝，调度器会把任务标为失败，不再把只有文字方案、没有文件改动的结果显示成“已完成”。Linux 从普通终端运行此模式需要按 Qwen Code 文档准备 Docker 或 Podman 沙箱。

API Key 通过只监听 `127.0.0.1` 的本机服务提交，保存在 macOS 钥匙串服务 `CodexTeam-Agent-Key` 中。Agent 配置、项目和日志只保存钥匙串条目的内部名称，不保存 Key。运行 Agent 时才从钥匙串读取并注入子进程环境。若同名 Agent 已经保存过 Key，更新模型时可以把 Key 留空。

前端使用固定的官方兼容端点：阿里百炼 Coding Plan 为 `https://coding.dashscope.aliyuncs.com/v1`，DeepSeek 为 `https://api.deepseek.com`，智谱 Coding 为 `https://open.bigmodel.cn/api/coding/paas/v4`。启动脚本不会自动安装 CLI，也不会把密钥写进项目。

## 命令行使用

在本文件所在目录打开终端。下面 `../codex-team-state` 用于保存账号和运行数据，必须在你的项目 Git 仓库之外，也不要把该目录上传或共享。

```bash
python3 codex_team.py --state ../codex-team-state login master
python3 codex_team.py --state ../codex-team-state login worker-1
python3 codex_team.py --state ../codex-team-state login worker-2
```

每次登录时，在浏览器中选择对应账号。需要设备码登录时在账号名称后加 `--device-auth`。不需要把密码或 token 写进配置。

复制 `team.example.json` 为 `team.json`，只需修改 `repo`、`goal` 和 Agent 列表。`master_account` 负责规划与验收，`worker_agents` 是执行池。支持的 `provider` 为 `codex`、`kimi`、`kimi-api`、`qwen`、`deepseek` 和 `zhipu`。`kimi-api`、`qwen`、`deepseek` 和 `zhipu` 通过 Qwen Code 运行，并使用 `model` 指定模型。旧版 `worker_accounts` 仍可继续使用，并自动视为 Codex Agent。

以后添加账号只需执行：

```bash
python3 codex_team.py --state ../codex-team-state login worker-3
```

然后把 `worker-3` 加入 `worker_agents`，并按需提高 `max_parallel_tasks`。不需要修改任务内容。

项目必须是已经有提交的 Git 仓库，运行前工作区需干净。工作目录从当前 HEAD 创建，未提交和忽略的文件不会被复制，依赖和本地配置需要按项目说明准备。

```bash
python3 codex_team.py --state ../codex-team-state run team.json
```

如果终端找不到 `codex`，可以加 `--codex /Applications/ChatGPT.app/Contents/Resources/codex`。Kimi 路径可用 `--kimi /绝对路径/kimi` 指定，Qwen Code 路径可用 `--qwen /绝对路径/qwen` 指定。自动规划可设置 `planner_model`，检查阶段可设置 `review_model`；单个执行 Agent 可以设置 `model`。

自动流程是：主账号读取目标并检查仓库，输出结构化任务计划；脚本为每个任务创建独立 Git worktree，并分配给子账号；全部任务完成后自动合并；主账号检查总目标、修复集成问题并测试。任务计划保存在本轮运行目录的 `plan.json`。

仍支持旧版手动模式：设置 `auto_plan` 为 `false` 或删除该字段，并提供带 `id`、`account`、`prompt` 的 `tasks` 数组和 `review_account`。

## 验收与结果

`checks` 配置实际的项目验收命令，每条为参数数组，例如 Python 项目：

```json
"checks": [["python3", "-m", "unittest", "discover"]]
```

命令不经过 shell；需要多个步骤请写成多条。检查账号会尝试测试，但仅有文字报告不代表验收通过。`checks` 为空时最终状态为 `needs_validation`；配置命令全部成功时为 `checks_passed`，其覆盖范围取决于你提供的检查。

运行完成后，终端输出集成目录和分支。原项目分支保持不变，可进入输出的 `integration` 目录查看或运行项目。检查结果后，在原项目自行执行 `git merge <输出的集成分支>`。脚本不会推送或部署。

每轮结果保存在 `state/runs/<运行编号>/`：

- `plan.json`：主账号自动生成的任务和分配结果（自动模式）。
- `status.json`：任务状态、执行账号、提交、分支、错误及报告。
- `logs/<任务>/`：提示词、事件流、错误日志和最终报告。
- `integration/`：完成合并的项目工作目录。
- `check-*.log`：配置的验收命令日志。

任务失败时不集成该轮任务；其他正在执行的并行任务会完成后再停止。合并冲突保留在 integration 目录，运行 `git status` 查看，手工解决并提交。脚本不自动恢复失败运行；再次 run 会开启新一轮。Codex 单次执行有超时限制，超时会结束对应进程组。账号锁避免本脚本同时使用同一个账号目录。

## 账号与隔离边界

Codex 别名使用独立 `CODEX_HOME` 和 file 凭据存储；Kimi 别名使用独立 `KIMI_CODE_HOME`。脚本不会复制当前 App 的登录信息。主账号可以加入执行 Agent 池，但同一轮最多承担一个执行任务；其他 Agent 列表不能重复。各 Agent 使用自己的权限与额度，额度或鉴权失败会报告错误。

仅添加你拥有或获准使用的账号，并遵守各账号所属组织的规则。不要用账号池规避额度、访问控制或其他平台限制。

账号文件包含登录凭据。目录权限设为仅当前用户访问；同一操作系统用户下的进程仍可能访问这些目录，Git worktree 也不是安全隔离容器。仅在可信项目上使用，需要强隔离时使用不同系统用户或容器。Codex 保留 workspace-write 沙箱，不自动批准沙箱之外的操作。

官方依据：

- [Codex 认证与凭据存储](https://developers.openai.com/codex/auth)
- [Codex 非交互执行](https://developers.openai.com/codex/noninteractive)
- [CODEX_HOME 配置位置](https://developers.openai.com/codex/config-advanced)
- [Kimi Code CLI](https://github.com/MoonshotAI/kimi-code)
- [Kimi 命令参考](https://github.com/MoonshotAI/kimi-code/blob/main/docs/en/reference/kimi-command.md)
- [Qwen Code 多 Provider 认证](https://github.com/QwenLM/qwen-code/blob/main/docs/users/configuration/auth.md)
- [Qwen Code 无界面模式](https://github.com/QwenLM/qwen-code/blob/main/docs/users/features/headless.md)

验证范围：交付前使用模拟 Codex、模拟 Kimi 和真实 Git 验证混合调度、合并、失败与冲突处理；未登录真实账号、未消耗模型额度。Kimi print 模式使用其 CLI 的自动权限策略，文件访问边界由 Kimi CLI 自身控制。
