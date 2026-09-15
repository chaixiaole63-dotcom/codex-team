#!/usr/bin/env python3
"""Launch Codex Team for the current project using saved UI preferences."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def command(args, cwd=None):
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def find_base():
    resolved = Path(__file__).resolve()
    for parent in resolved.parents:
        if (parent / 'codex_team.py').is_file() and (parent / 'server.py').is_file():
            return parent
    raise RuntimeError(
        '只安装了 Skill，没有找到 Codex Team 完整程序。'
        '请下载完整的 Codex Team 文件夹，再双击里面的 setup.command'
    )


def ensure_git(project):
    check = subprocess.run(['git', '-C', str(project), 'rev-parse', '--show-toplevel'],
                           text=True, capture_output=True)
    if check.returncode == 0:
        if Path(check.stdout.strip()).resolve() != project:
            raise RuntimeError('请先在 Codex 中打开整个项目文件夹，再从这个项目的对话中调用 Codex Team')
        return
    if project in (Path('/'), Path.home().resolve()):
        raise RuntimeError('不能把系统目录或用户主目录初始化为项目')
    command(['git', '-C', str(project), 'init'])
    command(['git', '-C', str(project), 'add', '-A'])
    command(['git', '-C', str(project), '-c', 'user.name=Codex Team',
             '-c', 'user.email=codex-team@localhost', 'commit', '--allow-empty',
             '-m', 'Initial snapshot before Codex collaboration'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('goal')
    parser.add_argument('--repo', default='.')
    args = parser.parse_args()
    base = find_base()
    state = base / 'codex-team-state'
    sibling_state = base.parent / 'codex-team' / 'codex-team-state'
    if not state.exists() and sibling_state.is_dir():
        state = sibling_state
    preferences_path = state / 'ui' / 'preferences.json'
    if not preferences_path.exists():
        raise RuntimeError(
            '还没有设置协作团队。请双击 Codex Team 文件夹里的 setup.command，'
            '在打开的页面选择主账号和执行 Agent，然后点“保存协作配置”'
        )
    preferences = json.loads(preferences_path.read_text())
    timeout_minutes = min(max(15, int(preferences.get('timeout_minutes', 120))), 480)
    project = Path(args.repo).expanduser().resolve()
    if not project.is_dir():
        raise RuntimeError('当前项目文件夹不存在，请重新在 Codex 中打开项目后再试')
    ensure_git(project)
    config = {
        'repo': str(project), 'goal': args.goal, 'timeout_seconds': timeout_minutes * 60,
        'auto_plan': True, 'master_account': preferences['master_account'],
        'worker_agents': preferences['worker_agents'],
        'max_parallel_tasks': preferences.get('max_parallel_tasks', len(preferences['worker_agents'])),
        'routing_policy': preferences.get('routing_policy', 'balanced'),
        'checks': preferences.get('checks', [])
    }
    config_path = state / 'ui' / 'configs' / f'skill-{uuid.uuid4().hex}.json'
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    codex = shutil.which('codex')
    app_codex = Path('/Applications/ChatGPT.app/Contents/Resources/codex')
    if not codex and app_codex.is_file():
        codex = str(app_codex)
    if not codex:
        raise RuntimeError('没有找到 Codex。请先安装并打开 Codex，登录后再试')
    local_bin = Path.home() / '.local' / 'bin'
    npm_bin = Path.home() / '.npm-global' / 'bin'
    kimi = shutil.which('kimi') or (str(local_bin / 'kimi') if (local_bin / 'kimi').is_file() else 'kimi')
    qwen = (shutil.which('qwen')
            or (str(npm_bin / 'qwen') if (npm_bin / 'qwen').is_file() else None)
            or (str(local_bin / 'qwen') if (local_bin / 'qwen').is_file() else 'qwen'))
    return subprocess.call([
        sys.executable, str(base / 'codex_team.py'), '--state', str(state),
        '--codex', codex, '--kimi', kimi, '--qwen', qwen,
        'run', str(config_path)
    ])


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as exc:
        print(f'没有完成：{exc}', file=sys.stderr)
        raise SystemExit(1)
