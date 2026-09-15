#!/usr/bin/env python3
"""Local multi-agent orchestration with a Codex lead and pluggable workers."""
import argparse
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager


def timeout_label(seconds):
    if seconds % 3600 == 0:
        return f'{seconds // 3600} 小时'
    return f'{seconds // 60} 分钟'


def run(args, cwd=None, env=None):
    p = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(f"命令失败 {args[0]} {args[1]}: {p.stderr.strip() or p.stdout.strip()}")
    return p.stdout.strip()


def git(path, *args):
    return run(['git', '-C', str(path), *args])


def save(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def normalized_usage(raw):
    if not isinstance(raw, dict):
        return None

    def value(*keys):
        for key in keys:
            candidate = raw.get(key)
            if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
                return max(0, int(candidate))
        return 0

    input_tokens = value('input_tokens', 'inputTokens', 'prompt_tokens', 'promptTokenCount')
    output_tokens = value('output_tokens', 'outputTokens', 'completion_tokens', 'candidatesTokenCount')
    reasoning_tokens = value(
        'reasoning_tokens', 'reasoning_output_tokens', 'thoughtTokens', 'thoughtsTokenCount'
    )
    cached_tokens = value(
        'cached_input_tokens', 'cachedTokens', 'cache_read_input_tokens',
        'cached_content_token_count', 'cachedContentTokenCount'
    )
    details = raw.get('input_tokens_details') or raw.get('prompt_tokens_details')
    if isinstance(details, dict):
        cached_tokens = max(cached_tokens, int(details.get('cached_tokens') or 0))
    total_tokens = value('total_tokens', 'totalTokens', 'totalTokenCount')
    if not total_tokens:
        total_tokens = input_tokens + output_tokens + reasoning_tokens
    if not any((input_tokens, output_tokens, reasoning_tokens, cached_tokens, total_tokens)):
        return None
    return {
        'input_tokens': input_tokens,
        'cached_input_tokens': cached_tokens,
        'output_tokens': output_tokens,
        'reasoning_tokens': reasoning_tokens,
        'total_tokens': total_tokens
    }


def save_usage(logs, provider, agent, model, raw):
    usage = normalized_usage(raw)
    if not usage:
        return None
    record = {'provider': provider, 'agent': agent, 'model': model, **usage}
    save(logs / 'usage.json', record)
    return record


def qwen_result(events):
    if not isinstance(events, list):
        raise ValueError('Qwen Code 返回的事件格式无效')
    final = next((event for event in reversed(events) if event.get('type') == 'result'), {})
    result = final.get('result') if isinstance(final.get('result'), str) else ''
    if not result:
        for event in reversed(events):
            message = event.get('message')
            if event.get('type') != 'assistant' or not isinstance(message, dict):
                continue
            content = message.get('content')
            if isinstance(content, list):
                result = '\n'.join(
                    part.get('text', '') for part in content
                    if isinstance(part, dict) and part.get('type') == 'text'
                )
            if result:
                break
    return result, final.get('usage')


def name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}', value):
        raise ValueError(f'无效名称: {value!r}')
    return value


def account_env(root, account):
    home = root / 'accounts' / name(account)
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    env = os.environ.copy()
    # Prevent ambient API credentials overriding the selected saved account.
    for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN'):
        env.pop(key, None)
    metadata = home / 'account.json'
    use_default = False
    if metadata.exists():
        try:
            use_default = bool(json.loads(metadata.read_text()).get('use_default_codex_home'))
        except (OSError, json.JSONDecodeError):
            pass
    if use_default:
        env.pop('CODEX_HOME', None)
    else:
        env['CODEX_HOME'] = str(home)
    return env


def kimi_env(root, agent):
    home = root / 'agents' / name(agent) / 'kimi-home'
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    env = os.environ.copy()
    env['KIMI_CODE_HOME'] = str(home)
    return env


def keychain_secret(account):
    result = subprocess.run(
        ['security', 'find-generic-password', '-w', '-s', 'CodexTeam-Agent-Key',
         '-a', name(account)], text=True, capture_output=True
    )
    if result.returncode or not result.stdout.strip():
        raise RuntimeError(f'无法从 macOS 钥匙串读取 Agent {account} 的 API Key')
    return result.stdout.strip()


def qwen_env(root, spec):
    env = os.environ.copy()
    env['QWEN_CODE_SUPPRESS_YOLO_WARNING'] = '1'
    qwen_home = root / 'agents' / name(spec['id']) / 'qwen-home'
    qwen_runtime = root / 'agents' / name(spec['id']) / 'qwen-runtime'
    for folder in (qwen_home, qwen_runtime):
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        folder.chmod(0o700)
    env['QWEN_HOME'] = str(qwen_home)
    env['QWEN_RUNTIME_DIR'] = str(qwen_runtime)
    # The coordinator supplies its own sandbox flag. Do not let a shell-level
    # override silently disable or replace that isolation.
    env.pop('QWEN_SANDBOX', None)
    if sys.platform == 'darwin':
        env.setdefault('SEATBELT_PROFILE', 'permissive-open')
    credential_id = spec.get('credential_id')
    if credential_id:
        env['OPENAI_API_KEY'] = keychain_secret(credential_id)
    if spec.get('base_url'):
        env['OPENAI_BASE_URL'] = spec['base_url']
    if spec.get('model'):
        env['OPENAI_MODEL'] = spec['model']
        env['QWEN_MODEL'] = spec['model']
    return env


@contextmanager
def account_lock(root, account):
    path = root / 'accounts' / name(account) / '.team.lock'
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f'账号 {account} 已被另一个任务使用')
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


@contextmanager
def agent_lock(root, agent):
    path = root / 'agent-locks' / f'{name(agent)}.lock'
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(f'Agent {agent} 已被另一个任务使用')
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def invoke(binary, root, account, workspace, prompt, logs, timeout, model=None,
           output_schema=None, sandbox='workspace-write'):
    logs.mkdir(parents=True, exist_ok=True)
    args = [binary, '-a', 'never', '-c', 'cli_auth_credentials_store="file"',
            'exec', '--sandbox', sandbox, '-C', str(workspace),
            '--json', '-o', str(logs / 'result.md')]
    if model:
        args.extend(['--model', model])
    if output_schema:
        args.extend(['--output-schema', str(output_schema)])
    args.append('-')
    (logs / 'prompt.txt').write_text(prompt)
    with account_lock(root, account), (logs / 'events.jsonl').open('w') as out, (logs / 'stderr.log').open('w') as err:
        proc = subprocess.Popen(args, env=account_env(root, account), stdin=subprocess.PIPE,
                                stdout=out, stderr=err, text=True, start_new_session=True)
        try:
            proc.communicate(prompt, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            except ProcessLookupError:
                pass
            raise RuntimeError(f'{account} 达到 {timeout_label(timeout)}执行上限') from exc
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            except ProcessLookupError:
                pass
            raise
    events = []
    for line in (logs / 'events.jsonl').read_text().splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    if proc.returncode:
        failure = next((event for event in reversed(events)
                        if event.get('type') in ('turn.failed', 'error')), None)
        detail = None
        if failure:
            error = failure.get('error')
            if isinstance(error, dict):
                detail = error.get('message')
            elif isinstance(error, str):
                detail = error
            detail = detail or failure.get('message')
        message = f'{account} 执行失败，退出码 {proc.returncode}'
        if detail:
            message += f'：{detail}'
        raise RuntimeError(f'{message}，日志: {logs}')
    usage_event = next((event for event in reversed(events) if isinstance(event.get('usage'), dict)), None)
    if usage_event:
        detected_model = model or usage_event.get('model')
        save_usage(logs, 'codex', account, detected_model, usage_event['usage'])
    if not any(e.get('type') == 'turn.completed' for e in events) or any(e.get('type') == 'turn.failed' for e in events):
        raise RuntimeError(f'{account} 未正常完成，检查日志: {logs}')
    result = logs / 'result.md'
    if not result.exists():
        raise RuntimeError(f'{account} 未生成结果报告')
    return result.read_text()


def invoke_kimi(binary, root, agent, workspace, prompt, logs, timeout, model=None):
    logs.mkdir(parents=True, exist_ok=True)
    command = [binary]
    if model:
        command.extend(['-m', model])
    command.extend(['-p', prompt])
    (logs / 'prompt.txt').write_text(prompt)
    with agent_lock(root, agent), (logs / 'result.md').open('w') as out, (logs / 'stderr.log').open('w') as err:
        proc = subprocess.Popen(command, cwd=workspace, env=kimi_env(root, agent),
                                stdout=out, stderr=err, text=True, start_new_session=True)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            except ProcessLookupError:
                pass
            raise RuntimeError(f'{agent} (Kimi) 达到 {timeout_label(timeout)}执行上限') from exc
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            except ProcessLookupError:
                pass
            raise
    if proc.returncode:
        raise RuntimeError(f'{agent} (Kimi) 执行失败，退出码 {proc.returncode}，日志: {logs}')
    result = (logs / 'result.md').read_text()
    if not result.strip():
        raise RuntimeError(f'{agent} (Kimi) 未生成结果报告')
    return result


def invoke_qwen(binary, root, spec, workspace, prompt, logs, timeout, model=None):
    logs.mkdir(parents=True, exist_ok=True)
    command = [binary, '-p', prompt, '--auth-type', 'openai', '--output-format', 'json',
               '--approval-mode', 'yolo', '--max-wall-time', f'{timeout}s']
    # A coordinator launched by the Codex skill already inherits the Codex OS
    # sandbox. macOS rejects nesting Qwen's Seatbelt sandbox inside it. Direct
    # terminal launches have no outer sandbox, so enable Qwen's own isolation.
    if not os.environ.get('CODEX_SANDBOX'):
        command.append('--sandbox')
    selected_model = model or spec.get('model')
    if selected_model:
        command.extend(['--model', selected_model])
    (logs / 'prompt.txt').write_text(prompt)
    events_path = logs / 'events.json'
    with agent_lock(root, spec['id']), events_path.open('w') as out, (logs / 'stderr.log').open('w') as err:
        proc = subprocess.Popen(command, cwd=workspace, env=qwen_env(root, spec),
                                stdout=out, stderr=err, text=True, start_new_session=True)
        try:
            proc.wait(timeout=timeout + 10)
        except BaseException:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            except ProcessLookupError:
                pass
            raise
    if proc.returncode:
        if proc.returncode == 55:
            raise RuntimeError(
                f"{spec['id']} ({spec['provider']}) 达到 {timeout_label(timeout)}执行上限"
            )
        raise RuntimeError(f"{spec['id']} ({spec['provider']}) 执行失败，退出码 {proc.returncode}，日志: {logs}")
    try:
        events = json.loads(events_path.read_text())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{spec['id']} ({spec['provider']}) 返回的事件不是有效 JSON") from exc
    try:
        result, raw_usage = qwen_result(events)
    except ValueError as exc:
        raise RuntimeError(f"{spec['id']} ({spec['provider']}) 返回的事件格式无效") from exc
    final = next((event for event in reversed(events) if event.get('type') == 'result'), {})
    denials = final.get('permission_denials') if isinstance(final, dict) else None
    if denials:
        blocked = sorted({
            item.get('tool_name', 'unknown') for item in denials if isinstance(item, dict)
        })
        detail = ', '.join(blocked) or 'unknown'
        raise RuntimeError(
            f"{spec['id']} ({spec['provider']}) 的必要操作被权限规则阻止: {detail}"
        )
    if isinstance(final, dict) and (final.get('is_error') or final.get('subtype') not in (None, 'success')):
        raise RuntimeError(f"{spec['id']} ({spec['provider']}) 未正常完成")
    if not result.strip():
        raise RuntimeError(f"{spec['id']} ({spec['provider']}) 未生成结果报告")
    (logs / 'result.md').write_text(result)
    save_usage(logs, spec['provider'], spec['id'], selected_model, raw_usage)
    return result


def worker_specs(config):
    raw = config.get('worker_agents')
    if raw is None:
        raw = [{'id': item, 'provider': 'codex', 'account': item}
               for item in config.get('worker_accounts', [])]
    if not isinstance(raw, list) or not raw:
        raise ValueError('worker_agents 必须包含至少一个 Agent')
    result = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError('worker_agents 的每项必须是对象')
        agent_id = name(item.get('id'))
        provider = item.get('provider', 'codex')
        if provider not in ('codex', 'kimi', 'kimi-api', 'qwen', 'deepseek', 'zhipu'):
            raise ValueError(f'暂不支持 Agent 类型: {provider}')
        spec = {'id': agent_id, 'provider': provider}
        if provider == 'codex':
            spec['account'] = name(item.get('account', agent_id))
        if item.get('model'):
            spec['model'] = str(item['model'])
        if item.get('base_url'):
            spec['base_url'] = str(item['base_url'])
        if item.get('credential_id'):
            spec['credential_id'] = name(item['credential_id'])
        result.append(spec)
    ids = [item['id'] for item in result]
    if len(ids) != len(set(ids)):
        raise ValueError('worker_agents 的 id 不能重复')
    return result


def invoke_agent(args, root, spec, workspace, prompt, logs, timeout, model=None):
    selected_model = model or spec.get('model')
    if spec['provider'] == 'codex':
        return invoke(args.codex, root, spec['account'], workspace, prompt, logs,
                      timeout, selected_model)
    if spec['provider'] == 'kimi':
        return invoke_kimi(args.kimi, root, spec['id'], workspace, prompt, logs,
                           timeout, selected_model)
    if spec['provider'] in ('kimi-api', 'qwen', 'deepseek', 'zhipu'):
        return invoke_qwen(args.qwen, root, spec, workspace, prompt, logs,
                           timeout, selected_model)
    raise ValueError(f"暂不支持 Agent 类型: {spec['provider']}")


def snapshot(workspace, message):
    git(workspace, 'add', '-A')
    if git(workspace, 'status', '--porcelain'):
        git(workspace, '-c', 'user.name=Codex Team', '-c', 'user.email=codex-team@localhost',
            'commit', '-m', message)
    return git(workspace, 'rev-parse', 'HEAD')


def validate_tasks(tasks, accounts):
    if not isinstance(tasks, list) or not tasks:
        raise ValueError('任务列表不能为空')
    ids = [name(t.get('id')) for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError('任务 id 必须唯一')
    for task in tasks:
        if not isinstance(task.get('prompt'), str) or not task['prompt'].strip():
            raise ValueError('每个任务需要非空 prompt')
    available = list(dict.fromkeys(name(account) for account in accounts))
    used = set()
    for task in tasks:
        requested = task.get('account')
        if requested:
            selected = name(requested)
            if selected not in available:
                raise ValueError(f'任务指定了不在执行池中的 Agent: {selected}')
        else:
            selected = next((account for account in available if account not in used), None)
            if selected is None:
                raise ValueError('并行任务数超过可用 Agent 数量')
        if selected in used:
            raise ValueError(f'同一轮并行任务不能重复使用 Agent: {selected}')
        task['account'] = selected
        used.add(selected)
    return tasks


def plan_tasks(args, root, config, repo, base, directory, master, worker_specs_list, timeout):
    workers = [item['id'] for item in worker_specs_list]
    maximum = int(config.get('max_parallel_tasks', len(workers)))
    maximum = min(maximum, len(workers))
    if maximum < 1:
        raise ValueError('max_parallel_tasks 必须为正数')
    schema = {
        'type': 'object',
        'properties': {
            'summary': {'type': 'string'},
            'tasks': {
                'type': 'array', 'minItems': 1, 'maxItems': maximum,
                'items': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'string', 'pattern': '^[a-zA-Z0-9][a-zA-Z0-9_-]{0,47}$'},
                        'title': {'type': 'string'},
                        'prompt': {'type': 'string'},
                        'account': {'type': 'string', 'enum': workers},
                        'routing_reason': {'type': 'string'}
                    },
                    'required': ['id', 'title', 'prompt', 'account', 'routing_reason'],
                    'additionalProperties': False
                }
            }
        },
        'required': ['summary', 'tasks'],
        'additionalProperties': False
    }
    schema_file = directory / 'plan-schema.json'
    save(schema_file, schema)
    workspace = directory / 'planning'
    git(repo, 'worktree', 'add', '--detach', str(workspace), base)
    routing_policy = config.get('routing_policy', 'balanced')
    if routing_policy not in ('cost', 'balanced', 'quality'):
        raise ValueError('routing_policy 必须是 cost、balanced 或 quality')
    routing_instructions = {
        'cost': (
            '成本优先：选择能够可靠完成任务的低成本 Agent。机械性检索、局部实现、测试和文档优先交给'
            'DeepSeek、Qwen、Kimi 或 GLM；复杂架构、跨模块推理、安全敏感修改才使用 Codex。'
            '把协调、重复上下文和最终复核也视为成本；不值得拆分时只生成一个任务。'
        ),
        'balanced': (
            '均衡：同时考虑质量、成本和时间。边界清晰的实现与测试优先交给合适的外部模型，'
            '复杂或高风险任务优先交给能力更强的 Agent；只并行真正独立的任务。'
        ),
        'quality': (
            '质量优先：为每项任务选择最擅长的 Agent，成本只作为次要因素。对架构、关键逻辑和跨模块修改'
            '优先使用能力更强的 Agent，同时仍避免没有收益的拆分。'
        )
    }[routing_policy]
    agent_summary = json.dumps([
        {
            'id': item['id'], 'provider': item['provider'], 'model': item.get('model'),
            'cost_hint': ('lower_cost_api' if item['provider'] in ('deepseek', 'kimi-api')
                          else 'subscription_or_plan')
        }
        for item in worker_specs_list
    ], ensure_ascii=False)
    prompt = (
        f"你是项目主账号，只负责分析和分工，不要修改任何文件。\n项目总目标：{config['goal']}\n"
        f"可用执行 Agent：{agent_summary}\n"
        f"路由要求：{routing_instructions}\n"
        f"请检查当前仓库，把目标拆成 1 到 {maximum} 个可以从同一基线并行完成的任务。"
        "不要创建有先后依赖的任务。每个任务的 prompt 必须写清楚实现目标、允许修改的目录或文件范围、"
        "与其他任务约定的接口和必须运行的测试。不同任务的写入范围不能重叠；如果无法安全并行，就只生成一个任务。"
        "根据任务难度、厂商、模型能力和路由要求为每个任务选择 account；同一 Agent 最多分配一个任务。"
        "routing_reason 用一句话说明为什么该 Agent 足以胜任且符合当前路由策略。"
        "任务 id 使用简短英文、数字、下划线或连字符。"
    )
    result = invoke(args.codex, root, master, workspace, prompt,
                    directory / 'logs' / 'planning', timeout,
                    config.get('planner_model'), schema_file, 'read-only')
    if git(workspace, 'rev-parse', 'HEAD') != base or git(workspace, 'status', '--porcelain'):
        raise RuntimeError('主账号在规划阶段修改了仓库，已停止运行')
    try:
        plan = json.loads(result)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'主账号返回的任务计划不是有效 JSON: {exc}') from exc
    tasks = validate_tasks(plan.get('tasks'), workers)
    plan['tasks'] = tasks
    save(directory / 'plan.json', plan)
    return tasks, plan


def execute(args, root):
    config = json.loads(Path(args.config).read_text())
    repo = Path(config['repo']).expanduser().resolve()
    timeout = int(config.get('timeout_seconds', 7200))
    if timeout < 1:
        raise ValueError('timeout_seconds 必须为正数')
    automatic = bool(config.get('auto_plan', False))
    if automatic:
        master = name(config['master_account'])
        specs = worker_specs(config)
        workers = [item['id'] for item in specs]
        reviewer = master
        known_accounts = [item['account'] for item in specs if item['provider'] == 'codex'] + [master]
    else:
        configured_tasks = config.get('tasks', [])
        configured_accounts = [name(t.get('account')) for t in configured_tasks]
        tasks = validate_tasks(configured_tasks, configured_accounts)
        if len(configured_accounts) != len(set(configured_accounts)):
            raise ValueError('手动并行任务的 account 必须唯一')
        reviewer = name(config['review_account'])
        known_accounts = configured_accounts + [reviewer]
        specs = [{'id': account, 'provider': 'codex', 'account': account}
                 for account in configured_accounts]
    specs_by_id = {item['id']: item for item in specs}
    repo = Path(git(repo, 'rev-parse', '--show-toplevel')).resolve()
    if root == repo or repo in root.parents:
        raise ValueError('--state 必须位于项目仓库之外')
    if git(repo, 'status', '--porcelain'):
        raise ValueError('请先提交或暂存保存工作区改动；项目必须干净')
    base = git(repo, 'rev-parse', 'HEAD')
    for account in sorted(set(known_accounts)):
        run([args.codex, '-c', 'cli_auth_credentials_store="file"', 'login', 'status'],
            env=account_env(root, account))
    if any(item['provider'] == 'kimi' for item in specs):
        run([args.kimi, '--version'])
    if any(item['provider'] in ('kimi-api', 'qwen', 'deepseek', 'zhipu') for item in specs):
        run([args.qwen, '--version'])
    run_id = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    directory = root / 'runs' / run_id
    directory.mkdir(parents=True)
    state = {'id': run_id, 'repo': str(repo), 'base': base,
             'mode': 'automatic' if automatic else 'manual',
             'routing_policy': config.get('routing_policy', 'balanced'),
             'status': 'planning' if automatic else 'running', 'tasks': {}}
    state_file = directory / 'status.json'
    save(state_file, state)
    print(f'运行目录: {directory}', flush=True)
    common = (f"项目目标：{config['goal']}\n"
              '遵循项目 AGENTS.md。仅完成分配的任务并运行相关检查。'
              '不要提交、切换分支、合并或推送，调度器负责 Git。'
              '最后报告修改、测试结果、未完成项。\n')
    try:
        if automatic:
            tasks, plan = plan_tasks(args, root, config, repo, base, directory,
                                     master, specs, timeout)
            planning_usage = directory / 'logs' / 'planning' / 'usage.json'
            if planning_usage.exists():
                state['planning_usage'] = json.loads(planning_usage.read_text())
            state['plan_summary'] = plan['summary']
            state['status'] = 'running'
            save(state_file, state)
            print(f"主账号生成 {len(tasks)} 个任务", flush=True)
        prepared = []
        for task in tasks:
            branch = f"codex-team/{run_id}/{task['id']}"
            workspace = directory / task['id']
            git(repo, 'worktree', 'add', '-b', branch, str(workspace), base)
            prepared.append((task, workspace))
            state['tasks'][task['id']] = {
                'title': task.get('title', task['id']), 'account': task['account'],
                'provider': specs_by_id[task['account']]['provider'],
                'model': specs_by_id[task['account']].get('model'),
                'routing_reason': task.get('routing_reason'),
                'branch': branch, 'workspace': str(workspace), 'status': 'pending'
            }
        save(state_file, state)
        failures = []
        for task, _ in prepared:
            state['tasks'][task['id']]['status'] = 'running'
        save(state_file, state)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures = {pool.submit(invoke_agent, args, root, specs_by_id[t['account']], w,
                       common + '\n你的任务：' + t['prompt'], directory / 'logs' / t['id'],
                       timeout, t.get('model')): (t, w) for t, w in prepared}
            for future in concurrent.futures.as_completed(futures):
                task, workspace = futures[future]
                entry = state['tasks'][task['id']]
                try:
                    entry['report'] = future.result()
                    usage_path = directory / 'logs' / task['id'] / 'usage.json'
                    if usage_path.exists():
                        entry['usage'] = json.loads(usage_path.read_text())
                    if git(workspace, 'rev-parse', 'HEAD') != base:
                        raise RuntimeError('任务自行修改了 Git HEAD，停止自动集成')
                    entry['commit'] = snapshot(workspace, f"team: {task['id']}")
                    entry['status'] = 'completed'
                except Exception as exc:
                    entry.update(status='failed', error=str(exc))
                    failures.append(task['id'])
                save(state_file, state)
                print(f"{task['id']}: {entry['status']}", flush=True)
        if failures:
            raise RuntimeError(f'任务失败，保留工作目录，未合并: {failures}')
        integration = directory / 'integration'
        branch = f'codex-team/{run_id}/integration'
        state.update(integration=str(integration), branch=branch, status='integrating')
        save(state_file, state)
        git(repo, 'worktree', 'add', '-b', branch, str(integration), base)
        for task in tasks:
            commit = state['tasks'][task['id']]['commit']
            git(integration, '-c', 'user.name=Codex Team', '-c', 'user.email=codex-team@localhost',
                'merge', '--no-edit', commit)
        reports = '\n\n'.join(f"{t}:\n{e['report']}" for t, e in state['tasks'].items())
        state['status'] = 'reviewing'
        save(state_file, state)
        invoke(args.codex, root, reviewer, integration,
               common + '\n你是项目主账号。检查已合并代码是否完整实现总目标，修复跨模块问题并运行项目测试。\n各任务报告：\n' + reports,
               directory / 'logs' / 'review', timeout, config.get('review_model'))
        review_usage = directory / 'logs' / 'review' / 'usage.json'
        if review_usage.exists():
            state['review_usage'] = json.loads(review_usage.read_text())
        snapshot(integration, 'team: integration review fixes')
        checks = config.get('checks', [])
        for i, command in enumerate(checks):
            if not isinstance(command, list) or not command or not all(isinstance(s, str) for s in command):
                raise ValueError('checks 的每项必须是非空字符串数组')
            with (directory / f'check-{i}.log').open('w') as log:
                proc = subprocess.run(command, cwd=integration, stdout=log, stderr=subprocess.STDOUT,
                                      timeout=timeout)
            if proc.returncode:
                raise RuntimeError(f'验收命令失败: {command}，见 check-{i}.log')
        if git(integration, 'status', '--porcelain'):
            raise RuntimeError('验收命令改变了文件，请检查集成目录')
        state['status'] = 'checks_passed' if checks else 'needs_validation'
        print(f"集成结果: {integration}\n分支: {branch}\n状态: {state['status']}", flush=True)
    except BaseException as exc:
        state.update(status='failed', error=str(exc))
        raise
    finally:
        save(state_file, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', required=True, help='仓库之外的私有账号和运行数据目录')
    parser.add_argument('--codex', default='codex', help='Codex CLI 可执行文件')
    parser.add_argument('--kimi', default='kimi', help='Kimi Code CLI 可执行文件')
    parser.add_argument('--qwen', default='qwen', help='Qwen Code CLI 可执行文件')
    sub = parser.add_subparsers(dest='action', required=True)
    login = sub.add_parser('login')
    login.add_argument('account')
    login.add_argument('--device-auth', action='store_true')
    run_parser = sub.add_parser('run')
    run_parser.add_argument('config')
    args = parser.parse_args()
    root = Path(args.state).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    if args.action == 'login':
        with account_lock(root, args.account):
            command = [args.codex, '-c', 'cli_auth_credentials_store="file"', 'login']
            if args.device_auth:
                command.append('--device-auth')
            return subprocess.call(command, env=account_env(root, args.account))
    execute(args, root)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as exc:
        print(f'停止: {exc}', file=sys.stderr)
        sys.exit(1)
