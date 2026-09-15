#!/bin/zsh
set -e

cd "${0:A:h}"

REPO_NAME="codex-team"
DESCRIPTION="本地多账号、多模型 Coding Agent 协作控制台：由 Codex 主账号规划、分工、集成和验收。"
SSH_KEY="$HOME/.ssh/id_ed25519_codex_team"

if nc -z 127.0.0.1 7890 >/dev/null 2>&1; then
  export HTTPS_PROXY="http://127.0.0.1:7890"
  export HTTP_PROXY="http://127.0.0.1:7890"
  if [[ -f "$SSH_KEY" ]]; then
    export GIT_SSH_COMMAND="ssh -i $SSH_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o 'ProxyCommand=nc -X connect -x 127.0.0.1:7890 %h %p'"
  fi
fi

git add -A

BLOCKED_FILES="$(git diff --cached --name-only | grep -E '(^|/)(codex-team-state/|team\.json$|\.env($|\.)|.*\.(pem|key)$)' || true)"
if [[ -n "$BLOCKED_FILES" ]]; then
  git reset >/dev/null
  echo "发现不应上传的本地配置或凭据，已停止同步："
  echo "$BLOCKED_FILES"
  read "?按回车关闭"
  exit 1
fi

if ! git diff --cached --quiet; then
  COMMIT_MESSAGE="${1:-Update Codex Team $(date '+%Y-%m-%d %H:%M')}"
  git commit -m "$COMMIT_MESSAGE"
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "没有找到 GitHub CLI。请先安装：brew install gh"
    read "?按回车关闭"
    exit 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    echo "首次使用需要登录 GitHub，浏览器会打开授权页面。"
    gh auth login --hostname github.com --git-protocol https --web
  fi
  echo "正在创建私有 GitHub 仓库 ${REPO_NAME}…"
  gh repo create "$REPO_NAME" --private --source=. --remote=origin \
    --description "$DESCRIPTION" --push
  gh repo edit --add-topic codex --add-topic multi-agent --add-topic coding-agents
else
  CURRENT_BRANCH="$(git branch --show-current)"
  if git ls-remote --exit-code --heads origin "$CURRENT_BRANCH" >/dev/null 2>&1; then
    git pull --rebase origin "$CURRENT_BRANCH"
  fi
  git push -u origin "$CURRENT_BRANCH"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh repo edit --description "$DESCRIPTION"
  fi
fi

echo "同步完成：$(git remote get-url origin)"
read "?按回车关闭"
