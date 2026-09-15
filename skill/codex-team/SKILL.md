---
name: codex-team
description: Use the locally configured Codex Team when the user asks several Codex accounts, Kimi, Qwen, DeepSeek, or GLM agents to work together on the current project. Also use for requests such as "让多个 Agent 一起做", "交给团队", or "多模型协作".
---

# Codex Team

Complete the user's requested outcome with the Agent team already saved in the local Codex Team settings.

Use the current workspace as the project. Pass the user's complete request to the launcher:

```bash
python3 ~/.codex/skills/codex-team/scripts/launch.py "<project goal>"
```

The launcher reads the saved team, prepares local version history when needed, and waits for planning, execution, integration, review, and checks. Do not ask the user to repeat a project path, account list, or model choice that is already available from the workspace and saved settings.

When it finishes, explain in plain Chinese:

- whether the task completed;
- where the completed version is located;
- which checks passed or what still needs attention.

Do not expose raw commands or internal configuration unless the user asks. Do not push, publish, or deploy unless the user asks.

If the launcher says no team is configured, tell the user: “请在 Codex Team 文件夹中双击 `setup.command`，在打开的页面选择主账号和执行 Agent，然后点‘保存协作配置’。设置一次后就能直接在项目对话中使用。”

If the local coordinator cannot be found, explain that installing only the Skill is insufficient because the Agent programs run on this Mac. Tell the user to download the complete Codex Team folder and double-click `setup.command`.
