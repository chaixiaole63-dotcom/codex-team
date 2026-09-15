#!/bin/zsh
set -e

cd "${0:A:h}"

echo ""
echo "Codex Team 首次设置"
echo "=================="
echo ""

if ! command -v python3 >/dev/null 2>&1; then
  echo "这台电脑还没有 Python 3。"
  echo "请先安装 Python 3，然后重新双击 setup.command。"
  read "?按回车关闭"
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  echo "这台电脑还没有 Git。"
  echo "请先安装 Apple 命令行工具，然后重新双击 setup.command。"
  echo "如果系统弹出安装窗口，按提示完成即可。"
  xcode-select --install >/dev/null 2>&1 || true
  read "?按回车关闭"
  exit 1
fi

CODEX_BIN="$(command -v codex 2>/dev/null)"
if [[ -z "$CODEX_BIN" && -x "/Applications/ChatGPT.app/Contents/Resources/codex" ]]; then
  CODEX_BIN="/Applications/ChatGPT.app/Contents/Resources/codex"
fi
if [[ -z "$CODEX_BIN" ]]; then
  echo "没有找到 Codex。"
  echo "请先安装并打开 Codex，登录账号后再重新双击 setup.command。"
  read "?按回车关闭"
  exit 1
fi

SKILLS_DIR="${CODEX_HOME:-$HOME/.codex}/skills"
mkdir -p "$SKILLS_DIR"
if [[ -e "$SKILLS_DIR/codex-team" && ! -L "$SKILLS_DIR/codex-team" ]]; then
  BACKUP="$SKILLS_DIR/codex-team.backup-$(date +%Y%m%d-%H%M%S)"
  mv "$SKILLS_DIR/codex-team" "$BACKUP"
  echo "原有 Skill 已备份到：$BACKUP"
fi
ln -sfn "$PWD/skill/codex-team" "$SKILLS_DIR/codex-team"

echo "Skill 已安装。"
echo "接下来会打开设置页面，请选择主账号和执行 Agent，然后点“保存协作配置”。"
echo "以后不用再运行这个文件；直接在 Codex 项目对话中输入 \$codex-team 即可。"
echo ""

exec "$PWD/start.command"
