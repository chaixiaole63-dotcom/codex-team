---
name: codex-team
description: Run the local Codex Team coordinator when the user asks multiple Codex accounts, Kimi Code, or other configured coding agents to collaborate on the current project.
---

# Codex Team

Use the local coordinator to complete the user's project goal with the Agent pool previously selected in the Codex Team web console.

Run this command from the target project directory, passing the user's full requested outcome as one argument:

```bash
python3 ~/.codex/skills/codex-team/scripts/launch.py "<project goal>"
```

If the skill is installed as a copied folder instead of the supplied symbolic link, run `scripts/launch.py` from this skill folder. The launcher finds the coordinator, reads the last saved Agent selection, creates a local Git baseline when needed, and waits for planning, parallel execution, integration, review, and checks to finish.

Report the integration directory, branch, final status, and any failure shown by the launcher. Do not merge the integration branch into the user's current branch or push it unless the user separately asks.

If no saved Agent selection exists, tell the user to open `start.command`, choose the main account and execution Agents, and click “保存协作配置”.
