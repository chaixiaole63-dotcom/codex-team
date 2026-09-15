#!/usr/bin/env python3
"""Build the self-contained Codex Team plugin from repository sources."""
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / 'plugins' / 'codex-team'


def copy_file(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def copy_tree(source, destination):
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        source, destination,
        ignore=shutil.ignore_patterns('.DS_Store', '__pycache__', '*.pyc')
    )


def main():
    copy_file(ROOT / 'codex_team.py', PLUGIN / 'codex_team.py')
    copy_file(ROOT / 'server.py', PLUGIN / 'server.py')
    copy_file(ROOT / 'start.command', PLUGIN / 'start.command')
    copy_file(ROOT / 'team.example.json', PLUGIN / 'team.example.json')
    copy_tree(ROOT / 'web', PLUGIN / 'web')
    copy_tree(ROOT / 'assets', PLUGIN / 'assets')
    copy_tree(ROOT / 'skill' / 'codex-team', PLUGIN / 'skills' / 'codex-team')
    print(f'Plugin 已生成：{PLUGIN}')


if __name__ == '__main__':
    main()
