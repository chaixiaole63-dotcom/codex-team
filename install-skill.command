#!/bin/zsh

cd "${0:A:h}"
echo "Codex Team 现在使用完整插件安装，接下来会自动安装 Skill、调度器和设置页面。"
exec "$PWD/setup.command"
