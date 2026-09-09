#!/bin/zsh
set -e
cd "${0:A:h}"
SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$SKILLS_DIR"
ln -sfn "$PWD/skill/codex-team" "$SKILLS_DIR/codex-team"
echo "已安装 Codex Team Skill：$SKILLS_DIR/codex-team"
echo '现在可以在 Codex 对话中输入：$codex-team 使用已配置的 Agent 一起完成当前项目'
read "?按回车关闭"
