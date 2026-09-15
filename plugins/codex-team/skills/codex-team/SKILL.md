---
name: codex-team
description: Use the locally configured Codex Team when the user asks several Codex accounts, Kimi, Qwen, DeepSeek, or GLM agents to work together on the current project. Also use for requests such as "让多个 Agent 一起做", "交给团队", or "多模型协作".
---

# Codex Team

Complete the user's requested outcome with the Agent team already saved in the local Codex Team settings.

Use the current workspace as the project. Resolve this Skill's own directory from the loaded `SKILL.md` path, then run its launcher with an absolute path and pass the user's complete request:

```bash
python3 <this-skill-directory>/scripts/launch.py "<project goal>"
```

The launcher reads the saved team, prepares local version history when needed, and waits for planning, execution, integration, review, and checks. Do not ask the user to repeat a project path, account list, or model choice that is already available from the workspace and saved settings.

When it finishes, explain in plain Chinese:

- whether the task completed;
- where the completed version is located;
- which checks passed or what still needs attention.

Do not expose raw commands or internal configuration unless the user asks. Do not push, publish, or deploy unless the user asks.

If the launcher opens the first-time settings page, tell the user: “设置页面已经打开。请选择主账号和执行 Agent，点‘保存，以后直接使用’，然后回到这里重新发送刚才的要求。”

If the local coordinator cannot be found, explain that an old standalone Skill was installed without the complete plugin. Tell the user to install the Codex Team plugin from its GitHub marketplace or download the complete folder and double-click `setup.command`.
