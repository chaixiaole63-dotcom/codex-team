#!/usr/bin/env python3
"""Local web UI for the Codex account orchestrator."""
import argparse
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import shlex
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
import webbrowser

from codex_team import account_env, kimi_env, name


BASE = Path(__file__).resolve().parent
WEB = BASE / 'web'
VERSION = '1.0.0'
TOKEN = secrets.token_urlsafe(24)
JOBS = {}
LOCK = threading.Lock()
STATE = None
CODEX = None
KIMI = None
QWEN = None
KEYCHAIN_SERVICE = 'CodexTeam-Agent-Key'

QWEN_PROVIDERS = {
    'kimi-api': {
        'label': 'Kimi 开放平台 API', 'model': 'kimi-k3',
        'base_url': 'https://api.moonshot.cn/v1'
    },
    'qwen': {
        'label': '阿里通义', 'model': 'qwen3-coder-plus',
        'base_url': 'https://coding.dashscope.aliyuncs.com/v1'
    },
    'deepseek': {
        'label': 'DeepSeek', 'model': 'deepseek-v4-pro',
        'base_url': 'https://api.deepseek.com'
    },
    'zhipu': {
        'label': '智谱 GLM', 'model': 'glm-5',
        'base_url': 'https://open.bigmodel.cn/api/coding/paas/v4'
    }
}

# CNY per 1M tokens. API prices are estimates and deliberately kept separate
# from subscription-backed providers, whose per-task incremental price is unknown.
PRICE_CATALOG = {
    ('kimi-api', 'kimi-k3'): {
        'input': 20.0, 'cached': 2.0, 'output': 100.0,
        'source': 'https://platform.kimi.com/docs/pricing/chat'
    },
    ('kimi-api', 'kimi-k2.7-code'): {
        'input': 6.5, 'cached': 1.3, 'output': 27.0,
        'source': 'https://platform.kimi.com/docs/pricing/chat'
    },
    ('kimi-api', 'kimi-k2.6'): {
        'input': 6.5, 'cached': 1.1, 'output': 27.0,
        'source': 'https://platform.kimi.com/docs/pricing/chat'
    },
    ('deepseek', 'deepseek-v4-flash'): {
        'input_min': 1.5, 'input_max': 3.0,
        'cached_min': 0.05, 'cached_max': 0.10,
        'output_min': 4.5, 'output_max': 9.0,
        'source': 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'
    },
    ('deepseek', 'deepseek-v4-flash-vision-exp'): {
        'input_min': 1.5, 'input_max': 3.0,
        'cached_min': 0.05, 'cached_max': 0.10,
        'output_min': 4.5, 'output_max': 9.0,
        'source': 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'
    },
    ('deepseek', 'deepseek-v4-pro'): {
        'input_min': 4.5, 'input_max': 9.0,
        'cached_min': 0.15, 'cached_max': 0.30,
        'output_min': 13.5, 'output_max': 27.0,
        'source': 'https://api-docs.deepseek.com/zh-cn/quick_start/pricing/'
    }
}
PRICE_UPDATED_AT = '2026-09-08'


def estimate_cost(provider, model, usage):
    pricing = PRICE_CATALOG.get((provider, model))
    if not pricing or not isinstance(usage, dict):
        return None
    input_tokens = max(0, int(usage.get('input_tokens') or 0))
    cached_tokens = min(input_tokens, max(0, int(usage.get('cached_input_tokens') or 0)))
    output_tokens = max(0, int(usage.get('output_tokens') or 0))
    reasoning_tokens = max(0, int(usage.get('reasoning_tokens') or 0))
    total_tokens = max(0, int(usage.get('total_tokens') or 0))
    if total_tokens > input_tokens + output_tokens:
        output_tokens += min(reasoning_tokens, total_tokens - input_tokens - output_tokens)
    uncached_tokens = max(0, input_tokens - cached_tokens)

    def calculate(input_price, cached_price, output_price):
        return (
            uncached_tokens * input_price
            + cached_tokens * cached_price
            + output_tokens * output_price
        ) / 1_000_000

    if 'input' in pricing:
        cost = calculate(pricing['input'], pricing['cached'], pricing['output'])
        return {'currency': 'CNY', 'min': cost, 'max': cost, 'source': pricing['source']}
    return {
        'currency': 'CNY',
        'min': calculate(pricing['input_min'], pricing['cached_min'], pricing['output_min']),
        'max': calculate(pricing['input_max'], pricing['cached_max'], pricing['output_max']),
        'source': pricing['source']
    }


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def agent_identity(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('请输入账号名称或邮箱')
    label = value.strip()
    if len(label) > 120:
        raise ValueError('账号名称不能超过 120 个字符')
    try:
        return name(label), label
    except ValueError:
        stem = re.sub(r'[^a-zA-Z0-9_-]+', '-', label).strip('-_').lower()
        if not stem:
            stem = 'agent'
        digest = hashlib.sha256(label.encode()).hexdigest()[:8]
        alias = f'{stem[:38].rstrip("-_")}-{digest}'
        return name(alias), label


def account_identity(auth_path):
    identity = {}
    try:
        auth = json.loads(auth_path.read_text())
        token = auth.get('tokens', {}).get('id_token')
        if not isinstance(token, str) or token.count('.') != 2:
            return identity
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        profile = claims.get('https://api.openai.com/auth', {})
        identity = {
            'email': claims.get('email'),
            'profile_name': claims.get('name'),
            'plan': profile.get('chatgpt_plan_type')
        }
        return {key: value for key, value in identity.items() if isinstance(value, str) and value}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}


def account_view(alias, auth_path, source, metadata=None):
    metadata = metadata or {}
    identity = account_identity(auth_path)
    label = identity.get('email') or identity.get('profile_name') or metadata.get('label')
    if not label:
        label = '当前 Codex' if source == 'default' else alias
    return {
        'name': alias, 'label': label, 'source': source, 'provider': 'codex',
        'has_credentials': auth_path.exists(), **identity
    }


def executable_available(command):
    if not command:
        return False
    if os.path.sep in command:
        return Path(command).is_file() and os.access(command, os.X_OK)
    return shutil.which(command) is not None


def keychain_has(account):
    if platform.system() != 'Darwin':
        return False
    result = subprocess.run(
        ['security', 'find-generic-password', '-s', KEYCHAIN_SERVICE,
         '-a', name(account)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return result.returncode == 0


def keychain_save(account, secret):
    if platform.system() != 'Darwin':
        raise ValueError('当前系统暂不支持前端保存 API Key')
    if not isinstance(secret, str) or not secret.strip():
        raise ValueError('首次添加该 Agent 时请输入 API Key')
    if len(secret) > 1000:
        raise ValueError('API Key 长度无效')
    result = subprocess.run(
        ['security', 'add-generic-password', '-U', '-s', KEYCHAIN_SERVICE,
         '-a', name(account), '-w', secret.strip()],
        text=True, capture_output=True
    )
    if result.returncode:
        raise RuntimeError('无法写入 macOS 钥匙串：' + (result.stderr.strip() or '未知错误'))


def qwen_profile_ready():
    folder = Path.home() / '.qwen'
    try:
        return folder.is_dir() and any(path.is_file() for path in folder.iterdir())
    except OSError:
        return False


def managed_agents():
    result = []
    folder = STATE / 'agents'
    if not folder.exists():
        return result
    for path in sorted(folder.iterdir()):
        metadata_path = path / 'agent.json'
        if not path.is_dir() or not metadata_path.exists():
            continue
        try:
            metadata = json.loads(metadata_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        provider = metadata.get('provider')
        if provider not in ('kimi', *QWEN_PROVIDERS):
            continue
        if provider == 'kimi':
            home = path / 'kimi-home'
            has_state = home.is_dir() and any(home.iterdir())
            installed = executable_available(KIMI)
            ready = has_state and installed
        else:
            installed = executable_available(QWEN)
            ready = installed and (keychain_has(path.name) or qwen_profile_ready())
        result.append({
            'name': path.name, 'label': metadata.get('label') or path.name,
            'source': 'managed', 'provider': provider,
            'model': metadata.get('model'), 'base_url': metadata.get('base_url'),
            'credential_id': metadata.get('credential_id'), 'has_credentials': ready,
            'installed': installed
        })
    return result


def job_record(job_id):
    path = STATE / 'ui' / 'jobs' / f'{job_id}.json'
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    with LOCK:
        process = JOBS.get(job_id)
    if process:
        code = process.poll()
        record['status'] = 'running' if code is None else ('completed' if code == 0 else 'failed')
        record['exit_code'] = code
        atomic_json(path, record)
        if code is not None:
            with LOCK:
                JOBS.pop(job_id, None)
    elif record.get('status') == 'running':
        record['status'] = 'interrupted'
        record['exit_code'] = None
        atomic_json(path, record)
    log = Path(record['log'])
    if log.exists():
        record['log_tail'] = log.read_text(errors='replace')[-12000:]
    else:
        record['log_tail'] = ''
    return record


def all_jobs():
    folder = STATE / 'ui' / 'jobs'
    if not folder.exists():
        return []
    records = [job_record(path.stem) for path in folder.glob('*.json')]
    return sorted((record for record in records if record), key=lambda item: item['created_at'], reverse=True)[:20]


def run_statistics():
    runs_folder = STATE / 'runs'
    summary = {
        'runs': 0, 'projects': 0, 'completed': 0, 'failed': 0,
        'active': 0, 'agent_tasks': 0, 'project_rows': [],
        'cost_cny_min': 0.0, 'cost_cny_max': 0.0,
        'price_updated_at': PRICE_UPDATED_AT
    }
    if not runs_folder.exists():
        return summary
    projects = {}
    completed_statuses = {'checks_passed', 'needs_validation'}
    active_statuses = {'planning', 'running', 'integrating', 'reviewing'}
    for status_path in runs_folder.glob('*/status.json'):
        try:
            data = json.loads(status_path.read_text())
            modified = int(status_path.stat().st_mtime)
        except (OSError, json.JSONDecodeError):
            continue
        repo = data.get('repo')
        if not isinstance(repo, str) or not repo:
            continue
        status = data.get('status', 'unknown')
        tasks = data.get('tasks') if isinstance(data.get('tasks'), dict) else {}
        summary['runs'] += 1
        summary['agent_tasks'] += len(tasks)
        if status in completed_statuses:
            summary['completed'] += 1
        elif status == 'failed':
            summary['failed'] += 1
        elif status in active_statuses:
            summary['active'] += 1
        entry = projects.setdefault(repo, {
            'path': repo, 'label': Path(repo).name or repo,
            'runs': 0, 'completed': 0, 'failed': 0, 'last_activity': 0,
            'models': {}
        })
        entry['runs'] += 1
        entry['completed'] += int(status in completed_statuses)
        entry['failed'] += int(status == 'failed')
        entry['last_activity'] = max(entry['last_activity'], modified)
        records = []
        for role in ('planning_usage', 'review_usage'):
            if isinstance(data.get(role), dict):
                records.append({**data[role], 'task_status': 'completed'})
        for task in tasks.values():
            if not isinstance(task, dict):
                continue
            usage = task.get('usage') if isinstance(task.get('usage'), dict) else {}
            records.append({
                'provider': usage.get('provider') or task.get('provider'),
                'model': usage.get('model') or task.get('model'),
                'task_status': task.get('status', 'unknown'),
                **usage
            })
        for usage in records:
            provider = usage.get('provider') or 'unknown'
            model = usage.get('model') or '默认模型'
            key = f'{provider}\0{model}'
            model_row = entry['models'].setdefault(key, {
                'provider': provider, 'model': model, 'tasks': 0,
                'input_tokens': 0, 'cached_input_tokens': 0,
                'output_tokens': 0, 'reasoning_tokens': 0, 'total_tokens': 0,
                'has_usage': False, 'pending': 0, 'running': 0,
                'completed': 0, 'failed': 0
            })
            model_row['tasks'] += 1
            task_status = usage.get('task_status')
            if task_status in ('pending', 'running', 'completed', 'failed'):
                model_row[task_status] += 1
            for field in ('input_tokens', 'cached_input_tokens', 'output_tokens',
                          'reasoning_tokens', 'total_tokens'):
                amount = usage.get(field)
                if isinstance(amount, (int, float)) and not isinstance(amount, bool):
                    model_row[field] += max(0, int(amount))
                    model_row['has_usage'] = True
    summary['projects'] = len(projects)
    all_project_rows = sorted(projects.values(), key=lambda item: item['last_activity'], reverse=True)
    for project in all_project_rows:
        model_rows = []
        for row in project.pop('models').values():
            cost = estimate_cost(row['provider'], row['model'], row) if row['has_usage'] else None
            if cost:
                row['cost'] = cost
                summary['cost_cny_min'] += cost['min']
                summary['cost_cny_max'] += cost['max']
                row['billing'] = 'api'
            elif row['provider'] in ('kimi-api', 'deepseek'):
                row['billing'] = 'api_unpriced'
            else:
                row['billing'] = 'subscription'
            model_rows.append(row)
        project['models'] = sorted(
            model_rows, key=lambda item: (item['total_tokens'], item['tasks']), reverse=True
        )
    summary['project_rows'] = all_project_rows[:8]
    return summary


def default_account():
    environment = os.environ.copy()
    for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN', 'CODEX_HOME'):
        environment.pop(key, None)
    result = subprocess.run(
        [CODEX, 'login', 'status'], env=environment,
        text=True, capture_output=True, timeout=10
    )
    if result.returncode:
        return None
    home = STATE / 'accounts' / 'current'
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_json(home / 'account.json', {'use_default_codex_home': True})
    view = account_view('current', Path.home() / '.codex' / 'auth.json', 'default')
    view['has_credentials'] = True
    return view


def saved_projects():
    projects = {}
    database = Path.home() / '.codex' / 'state_5.sqlite'
    if database.exists():
        try:
            connection = sqlite3.connect(f'file:{database}?mode=ro', uri=True, timeout=1)
            rows = connection.execute(
                'SELECT p.name, r.path FROM projects p '
                'JOIN project_roots r ON r.project_id = p.id ORDER BY p.position, r.position'
            ).fetchall()
            connection.close()
            for label, raw_path in rows:
                path = Path(raw_path).expanduser()
                if path.is_dir():
                    projects[str(path.resolve())] = label
        except sqlite3.Error:
            pass
    configs = STATE / 'ui' / 'configs'
    if configs.exists():
        for config_path in sorted(configs.glob('*.json'), key=lambda path: path.stat().st_mtime, reverse=True):
            try:
                raw_path = json.loads(config_path.read_text()).get('repo')
                path = Path(raw_path).expanduser()
                if path.is_dir():
                    projects.setdefault(str(path.resolve()), path.name)
            except (OSError, TypeError, json.JSONDecodeError):
                pass
    result = []
    for path, label in projects.items():
        result.append({'label': label, 'path': path, 'is_git': is_git_project(Path(path))})
    return result


def is_git_project(path):
    check = subprocess.run(
        ['git', '-C', str(path), 'rev-parse', '--show-toplevel'],
        text=True, capture_output=True
    )
    if check.returncode:
        return False
    try:
        return Path(check.stdout.strip()).resolve() == path.resolve()
    except OSError:
        return False


def prepare_git_project(raw_path):
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError('请先选择项目目录')
    project = Path(raw_path).expanduser().resolve()
    if not project.is_dir():
        raise ValueError('项目目录不存在')
    if project in (Path('/'), Path.home().resolve()):
        raise ValueError('不能把整个系统目录或用户主目录初始化为项目')
    if is_git_project(project):
        return {'path': str(project), 'is_git': True, 'already_ready': True}
    commands = [
        ['git', '-C', str(project), 'init'],
        ['git', '-C', str(project), 'add', '-A'],
        ['git', '-C', str(project), '-c', 'user.name=Codex Team',
         '-c', 'user.email=codex-team@localhost', 'commit', '--allow-empty',
         '-m', 'Initial snapshot before Codex collaboration']
    ]
    for command in commands:
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(f'Git 初始化失败：{detail}')
    return {'path': str(project), 'is_git': True, 'already_ready': False}


def launch_job(kind, command, env=None, metadata=None):
    job_id = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    folder = STATE / 'ui' / 'jobs'
    folder.mkdir(parents=True, exist_ok=True)
    log = folder / f'{job_id}.log'
    output = log.open('w')
    try:
        process = subprocess.Popen(
            command, cwd=BASE, env=env, stdin=subprocess.DEVNULL,
            stdout=output, stderr=subprocess.STDOUT, text=True,
            start_new_session=True
        )
    finally:
        output.close()
    record = {
        'id': job_id, 'kind': kind, 'status': 'running',
        'created_at': int(time.time()), 'log': str(log)
    }
    if metadata:
        record.update(metadata)
    atomic_json(folder / f'{job_id}.json', record)
    with LOCK:
        JOBS[job_id] = process
    return record


def snapshot():
    accounts_dir = STATE / 'accounts'
    accounts = []
    if accounts_dir.exists():
        for path in sorted(accounts_dir.iterdir()):
            if path.is_dir():
                metadata = {}
                metadata_path = path / 'account.json'
                if metadata_path.exists():
                    try:
                        metadata = json.loads(metadata_path.read_text())
                    except (OSError, json.JSONDecodeError):
                        pass
                if metadata.get('use_default_codex_home'):
                    continue
                accounts.append(account_view(path.name, path / 'auth.json', 'managed', metadata))
    try:
        current = default_account()
    except (OSError, subprocess.TimeoutExpired):
        current = None
    if current:
        accounts.insert(0, current)
    accounts.extend(managed_agents())
    preferences = {}
    preferences_path = STATE / 'ui' / 'preferences.json'
    if preferences_path.exists():
        try:
            preferences = json.loads(preferences_path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return {
        'version': VERSION,
        'accounts': accounts, 'preferences': preferences, 'jobs': all_jobs(),
        'statistics': run_statistics(),
        'capabilities': {
            'python': sys.version_info >= (3, 9), 'git': executable_available('git'),
            'codex': executable_available(CODEX), 'kimi': executable_available(KIMI),
            'qwen': executable_available(QWEN), 'qwen_profile': qwen_profile_ready()
        }
    }


def normalize_worker_agents(worker_agents):
    if not isinstance(worker_agents, list) or not worker_agents:
        raise ValueError('至少选择一个执行 Agent')
    normalized = []
    for item in worker_agents:
        if not isinstance(item, dict):
            raise ValueError('执行 Agent 配置无效')
        agent_id = name(item.get('id'))
        provider = item.get('provider')
        if provider not in ('codex', 'kimi', *QWEN_PROVIDERS):
            raise ValueError(f'暂不支持 Agent 类型：{provider}')
        if provider == 'kimi' and not executable_available(KIMI):
            raise ValueError('已选择 Kimi Agent，但未检测到 Kimi Code CLI')
        if provider in QWEN_PROVIDERS and not executable_available(QWEN):
            raise ValueError('已选择 API Agent，但未检测到 Qwen Code CLI')
        entry = {'id': agent_id, 'provider': provider}
        if provider == 'codex':
            entry['account'] = name(item.get('account', agent_id))
        if item.get('model'):
            entry['model'] = str(item['model'])
        if provider in QWEN_PROVIDERS:
            metadata_path = STATE / 'agents' / agent_id / 'agent.json'
            if not metadata_path.exists():
                raise ValueError(f'找不到 Agent 配置：{agent_id}')
            metadata = json.loads(metadata_path.read_text())
            if metadata.get('provider') != provider:
                raise ValueError(f'Agent 类型不匹配：{agent_id}')
            entry['model'] = metadata.get('model') or entry.get('model')
            entry['base_url'] = metadata.get('base_url')
            entry['credential_id'] = metadata.get('credential_id')
        normalized.append(entry)
    ids = [item['id'] for item in normalized]
    if len(ids) != len(set(ids)):
        raise ValueError('执行 Agent 不能重复')
    return normalized


class Handler(BaseHTTPRequestHandler):
    server_version = 'CodexTeamUI/1.0'

    def log_message(self, fmt, *args):
        sys.stderr.write('%s - %s\n' % (self.address_string(), fmt % args))

    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        return secrets.compare_digest(self.headers.get('X-Team-Token', ''), TOKEN)

    def read_json(self):
        length = int(self.headers.get('Content-Length', 0))
        if length > 1024 * 1024:
            raise ValueError('请求过大')
        return json.loads(self.rfile.read(length) or b'{}')

    def do_GET(self):
        if self.path == '/':
            body = (WEB / 'index.html').read_text().replace('__API_TOKEN__', TOKEN).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path in ('/styles.css', '/app.js', '/favicon.svg'):
            path = WEB / self.path.lstrip('/')
            body = path.read_bytes()
            content_types = {
                '.css': 'text/css; charset=utf-8',
                '.js': 'text/javascript; charset=utf-8',
                '.svg': 'image/svg+xml'
            }
            content_type = content_types[path.suffix]
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == '/api/snapshot':
            if not self.authorized():
                return self.send_json(403, {'error': '无效请求'})
            return self.send_json(200, snapshot())
        self.send_error(404)

    def do_POST(self):
        if not self.authorized():
            return self.send_json(403, {'error': '无效请求'})
        try:
            data = self.read_json()
            if self.path == '/api/login':
                account, display_label = agent_identity(data.get('account'))
                provider = data.get('provider', 'codex')
                if provider == 'kimi' and (STATE / 'accounts' / account).exists():
                    raise ValueError('这个别名已被 Codex 账号使用，请换一个别名')
                if provider != 'codex' and (STATE / 'accounts' / account).exists():
                    raise ValueError('这个别名已被 Codex 账号使用，请换一个别名')
                if provider == 'codex' and (STATE / 'agents' / account / 'agent.json').exists():
                    raise ValueError('这个别名已被其他 Agent 使用，请换一个别名')
                if provider == 'codex':
                    atomic_json(STATE / 'accounts' / account / 'account.json', {
                        'label': display_label
                    })
                    command = [CODEX, '-c', 'cli_auth_credentials_store="file"', 'login']
                    if data.get('device_auth'):
                        command.append('--device-auth')
                    environment = account_env(STATE, account)
                elif provider == 'kimi':
                    if not executable_available(KIMI):
                        raise ValueError('未检测到 Kimi Code CLI，请先安装后重启控制台')
                    atomic_json(STATE / 'agents' / account / 'agent.json', {
                        'provider': 'kimi', 'label': display_label
                    })
                    command = [KIMI, 'login']
                    environment = kimi_env(STATE, account)
                elif provider in QWEN_PROVIDERS:
                    if not executable_available(QWEN):
                        raise ValueError('未检测到 Qwen Code CLI，请先安装后重启控制台')
                    definition = QWEN_PROVIDERS[provider]
                    model = str(data.get('model') or definition['model']).strip()
                    if not model or len(model) > 100:
                        raise ValueError('模型名称无效')
                    api_key = data.get('api_key', '')
                    if api_key:
                        keychain_save(account, api_key)
                    elif not keychain_has(account):
                        raise ValueError('首次添加该 Agent 时请输入 API Key')
                    atomic_json(STATE / 'agents' / account / 'agent.json', {
                        'provider': provider, 'label': display_label, 'model': model,
                        'base_url': definition['base_url'], 'credential_id': account
                    })
                    command = [QWEN, '--version']
                    environment = os.environ.copy()
                else:
                    raise ValueError(f'暂不支持 Agent 类型：{provider}')
                record = launch_job(
                    'login', command, environment,
                    {'account': account, 'provider': provider, 'label': f'登录 {display_label}'}
                )
                return self.send_json(202, record)
            if self.path == '/api/preferences':
                master = name(data.get('master_account'))
                normalized = normalize_worker_agents(data.get('worker_agents', []))
                routing_policy = str(data.get('routing_policy', 'balanced'))
                if routing_policy not in ('cost', 'balanced', 'quality'):
                    raise ValueError('模型路由策略无效')
                maximum = min(
                    max(1, int(data.get('max_parallel_tasks', len(normalized)))),
                    len(normalized)
                )
                timeout_minutes = min(max(15, int(data.get('timeout_minutes', 120))), 480)
                preferences = {
                    'master_account': master,
                    'worker_agents': normalized,
                    'max_parallel_tasks': maximum,
                    'routing_policy': routing_policy,
                    'timeout_minutes': timeout_minutes,
                    'checks': []
                }
                atomic_json(STATE / 'ui' / 'preferences.json', preferences)
                return self.send_json(200, {'saved': True, 'preferences': preferences})
            if self.path == '/api/pick-project':
                if platform.system() != 'Darwin':
                    raise ValueError('当前系统不支持目录选择器，请直接输入绝对路径')
                selected = subprocess.run(
                    ['osascript', '-e', 'POSIX path of (choose folder with prompt "选择 Git 项目")'],
                    text=True, capture_output=True
                )
                if selected.returncode:
                    raise ValueError('没有选择项目目录')
                path = Path(selected.stdout.strip().rstrip('/')).resolve()
                return self.send_json(200, {'path': str(path), 'is_git': is_git_project(path)})
            if self.path == '/api/prepare-git':
                return self.send_json(200, prepare_git_project(data.get('path', '')))
            if self.path == '/api/start':
                repo = Path(data.get('repo', '')).expanduser().resolve()
                if not repo.is_dir():
                    raise ValueError('项目目录不存在')
                check_repo = subprocess.run(
                    ['git', '-C', str(repo), 'rev-parse', '--show-toplevel'],
                    text=True, capture_output=True
                )
                if check_repo.returncode:
                    raise ValueError('选择的目录不是 Git 项目')
                goal = data.get('goal', '').strip()
                if len(goal) < 4:
                    raise ValueError('请写清楚项目目标')
                master = name(data.get('master_account'))
                normalized = normalize_worker_agents(data.get('worker_agents', []))
                routing_policy = str(data.get('routing_policy', 'balanced'))
                if routing_policy not in ('cost', 'balanced', 'quality'):
                    raise ValueError('模型路由策略无效')
                checks = []
                for line in data.get('checks', '').splitlines():
                    if line.strip():
                        checks.append(shlex.split(line))
                timeout_minutes = min(max(15, int(data.get('timeout_minutes', 120))), 480)
                config = {
                    'repo': str(repo), 'goal': goal, 'timeout_seconds': timeout_minutes * 60,
                    'auto_plan': True, 'master_account': master,
                    'worker_agents': normalized,
                    'max_parallel_tasks': min(max(1, int(data.get('max_parallel_tasks', len(normalized)))), len(normalized)),
                    'routing_policy': routing_policy,
                    'timeout_minutes': timeout_minutes,
                    'checks': checks
                }
                config_id = uuid.uuid4().hex
                config_path = STATE / 'ui' / 'configs' / f'{config_id}.json'
                atomic_json(config_path, config)
                atomic_json(STATE / 'ui' / 'preferences.json', {
                    'master_account': master,
                    'worker_agents': normalized,
                    'max_parallel_tasks': config['max_parallel_tasks'],
                    'routing_policy': routing_policy,
                    'timeout_minutes': timeout_minutes,
                    'checks': checks
                })
                record = launch_job(
                    'run',
                    [sys.executable, str(BASE / 'codex_team.py'), '--state', str(STATE),
                     '--codex', CODEX, '--kimi', KIMI, '--qwen', QWEN,
                     'run', str(config_path)],
                    metadata={'label': goal[:80], 'repo': str(repo)}
                )
                return self.send_json(202, record)
            self.send_error(404)
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            self.send_json(400, {'error': str(exc)})
        except Exception as exc:
            self.send_json(500, {'error': f'操作失败：{exc}'})


def main():
    global STATE, CODEX, KIMI, QWEN
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', default=str(BASE / 'codex-team-state'))
    parser.add_argument('--codex', default='codex')
    parser.add_argument('--kimi', default='kimi')
    parser.add_argument('--qwen', default='qwen')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args()
    STATE = Path(args.state).expanduser().resolve()
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.chmod(0o700)
    CODEX = args.codex
    KIMI = args.kimi
    QWEN = args.qwen
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://127.0.0.1:{args.port}/'
    print(f'Codex Team 控制台：{url}', flush=True)
    if not args.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n控制台已停止')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
