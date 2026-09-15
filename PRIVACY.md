# Codex Team 隐私说明

Codex Team 默认在用户自己的电脑上运行。

## 保存在哪里

- Codex 与 Kimi 的登录状态保存在本机专用目录中。
- API Key 保存在 macOS 系统钥匙串中。
- 团队设置、运行日志和用量统计保存在 `~/.codex/codex-team-data`。
- 项目文件保留在用户选择的项目和本地临时工作区中。

## 会发送什么

执行任务时，所选 Agent 会按照各自产品的工作方式，把完成任务所需的提示和项目内容发送给对应服务商。Codex Team 不会再把这些内容发送到自己的服务器，因为本项目不运行独立的云端服务。

GitHub 同步只同步程序源代码和文档。账号状态、API Key、团队设置、项目记录和运行日志均被排除。

## 删除数据

双击 `uninstall.command` 可从 Codex 移除插件，并保留本地设置，方便以后重新安装。需要彻底删除时，还应删除 `~/.codex/codex-team-data`，并在 macOS“钥匙串访问”中删除服务名为 `CodexTeam-Agent-Key` 的条目。
