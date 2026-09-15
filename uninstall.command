#!/bin/zsh
set -e

CODEX_BIN="$(command -v codex 2>/dev/null)"
if [[ -z "$CODEX_BIN" && -x "/Applications/ChatGPT.app/Contents/Resources/codex" ]]; then
  CODEX_BIN="/Applications/ChatGPT.app/Contents/Resources/codex"
fi

if [[ -n "$CODEX_BIN" ]]; then
  "$CODEX_BIN" plugin remove codex-team@codex-team-marketplace >/dev/null 2>&1 || true
fi

LEGACY_SKILL="${CODEX_HOME:-$HOME/.codex}/skills/codex-team"
if [[ -L "$LEGACY_SKILL" ]]; then
  rm "$LEGACY_SKILL"
fi

echo "Codex Team 已从 Codex 中移除。"
echo "账号登录、API Key 和运行记录仍保留在这台 Mac，重新安装后可以继续使用。"
echo "如需彻底清除，请在系统钥匙串和 ~/.codex/codex-team-data 中手动删除相应数据。"
read "?按回车关闭"
