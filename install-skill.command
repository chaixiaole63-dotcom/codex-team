#!/bin/zsh
set -e
cd "${0:A:h}"
SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$SKILLS_DIR"
if [[ -e "$SKILLS_DIR/codex-team" && ! -L "$SKILLS_DIR/codex-team" ]]; then
  BACKUP="$SKILLS_DIR/codex-team.backup-$(date +%Y%m%d-%H%M%S)"
  mv "$SKILLS_DIR/codex-team" "$BACKUP"
  echo "原有 Skill 已备份到：$BACKUP"
fi
ln -sfn "$PWD/skill/codex-team" "$SKILLS_DIR/codex-team"
echo "已安装 Codex Team Skill：$SKILLS_DIR/codex-team"
echo '现在可以在 Codex 对话中输入：$codex-team 使用已配置的 Agent 一起完成当前项目'
echo "如果还没有配置账号，请双击 setup.command，它会安装 Skill 并打开设置页面。"
read "?按回车关闭"
