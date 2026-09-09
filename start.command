#!/bin/zsh
cd "${0:A:h}"
STATE_DIR="./codex-team-state"
if [[ ! -d "$STATE_DIR" && -d "../codex-team/codex-team-state" ]]; then
  STATE_DIR="../codex-team/codex-team-state"
fi
CODEX_BIN="$(command -v codex 2>/dev/null)"
if [[ -z "$CODEX_BIN" && -x "/Applications/ChatGPT.app/Contents/Resources/codex" ]]; then
  CODEX_BIN="/Applications/ChatGPT.app/Contents/Resources/codex"
fi
if [[ -z "$CODEX_BIN" ]]; then
  echo "没有找到 Codex CLI，请先安装 Codex。"
  read "?按回车关闭"
  exit 1
fi
KIMI_BIN="$(command -v kimi 2>/dev/null)"
if [[ -z "$KIMI_BIN" && -x "$HOME/.local/bin/kimi" ]]; then
  KIMI_BIN="$HOME/.local/bin/kimi"
fi
if [[ -z "$KIMI_BIN" ]]; then
  KIMI_BIN="kimi"
fi
QWEN_BIN="$(command -v qwen 2>/dev/null)"
if [[ -z "$QWEN_BIN" && -x "$HOME/.npm-global/bin/qwen" ]]; then
  QWEN_BIN="$HOME/.npm-global/bin/qwen"
fi
if [[ -z "$QWEN_BIN" && -x "$HOME/.local/bin/qwen" ]]; then
  QWEN_BIN="$HOME/.local/bin/qwen"
fi
if [[ -z "$QWEN_BIN" ]]; then
  QWEN_BIN="qwen"
fi
python3 server.py --state "$STATE_DIR" --codex "$CODEX_BIN" --kimi "$KIMI_BIN" --qwen "$QWEN_BIN"
