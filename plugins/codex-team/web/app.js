const token = document.querySelector('meta[name="team-token"]').content;
const headers = {'Content-Type': 'application/json', 'X-Team-Token': token};
let snapshotTimer;
const agentStates = new Map();
const providerNames = {
  codex: 'Codex', kimi: 'Kimi 账号', 'kimi-api': 'Kimi API', qwen: '阿里通义',
  deepseek: 'DeepSeek', zhipu: '智谱 GLM'
};
const providerModels = {
  'kimi-api': 'kimi-k3', qwen: 'qwen3-coder-plus', deepseek: 'deepseek-v4-pro', zhipu: 'glm-5'
};

async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {...headers, ...(options.headers || {})}});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '请求失败');
  return data;
}

function selectedWorkers() {
  return [...document.querySelectorAll('input[name="worker"]:checked')].map(input => input.value);
}

function renderAccounts(accounts, capabilities = {}, preferences = {}) {
  const list = document.querySelector('#accounts');
  const master = document.querySelector('#master');
  const previousMaster = master.value || preferences.master_account || '';
  const selectedBeforeRender = selectedWorkers();
  const preferredWorkers = (preferences.worker_agents || []).map(item => item.id);
  list.replaceChildren();
  master.innerHTML = '<option value="">选择主账号</option>';
  agentStates.clear();
  for (const account of accounts) {
    agentStates.set(account.name, account);
    const fragment = document.querySelector('#account-template').content.cloneNode(true);
    const label = account.label || account.name;
    fragment.querySelector('.avatar').textContent = label.slice(0, 2).toUpperCase();
    fragment.querySelector('strong').textContent = label;
    const provider = providerNames[account.provider] || account.provider;
    const model = account.model ? ' · ' + account.model : '';
    const plan = account.plan ? ' · ' + account.plan : '';
    fragment.querySelector('small').textContent = account.source === 'default'
      ? 'Codex · 当前登录 · 凭据已配置' + plan
      : (account.has_credentials ? provider + model + ' · 凭据已配置 · ' + account.name + plan : provider + model + ' · 等待配置 · ' + account.name);
    const statusDot = fragment.querySelector('.status-dot');
    statusDot.classList.toggle('ready', account.has_credentials);
    statusDot.title = account.has_credentials
      ? '凭据已配置；未检测实时网络、账户额度或模型响应'
      : '尚未配置可用凭据';
    list.append(fragment);
    if (account.provider === 'codex' && account.has_credentials) {
      const option = document.createElement('option');
      option.value = account.name;
      option.textContent = label;
      master.append(option);
    }
  }
  if (accounts.some(account => account.name === previousMaster)) master.value = previousMaster;
  document.querySelector('#account-count').textContent = accounts.length;

  const oldWorkers = selectedBeforeRender.length ? selectedBeforeRender : preferredWorkers;
  const workerList = document.querySelector('#worker-list');
  workerList.replaceChildren();
  const available = accounts.filter(account => account.has_credentials);
  if (!available.length) {
    workerList.innerHTML = '<div class="empty-inline">至少添加一个可用的执行 Agent</div>';
  } else {
    for (const account of available) {
      const label = document.createElement('label');
      label.className = 'worker-choice';
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.name = 'worker';
      input.value = account.name;
      input.checked = oldWorkers.includes(account.name);
      const span = document.createElement('span');
      const isMaster = account.provider === 'codex' && account.name === master.value;
      span.textContent = providerNames[account.provider] + ' · ' + (account.label || account.name) +
        (isMaster ? '（主账号）' : '');
      label.append(input, span);
      workerList.append(label);
    }
  }
  const kimiOption = document.querySelector('#agent-provider option[value="kimi"]');
  kimiOption.disabled = false;
  kimiOption.textContent = capabilities.kimi ? 'Kimi 账号登录' : 'Kimi 账号登录（添加前需安装 Kimi Code）';
  for (const provider of ['kimi-api', 'qwen', 'deepseek', 'zhipu']) {
    const option = document.querySelector(`#agent-provider option[value="${provider}"]`);
    option.disabled = false;
    option.textContent = providerNames[provider] + (capabilities.qwen ? '' : '（添加前需安装 Qwen Code）');
  }
  document.querySelector('#agent-note').textContent = capabilities.qwen
    ? 'Kimi 可选择账号登录或开放平台 API；API Agent 可直接填写模型和 Key。'
    : '可以先选择厂商查看配置项；正式添加前需要安装对应的 Kimi 或 Qwen Code CLI。';
}

function renderHealth(capabilities = {}, version = '') {
  const checks = [
    ['Python', capabilities.python, true],
    ['Git', capabilities.git, true],
    ['Codex', capabilities.codex, true],
    ['Kimi Code', capabilities.kimi, false],
    ['Qwen Code', capabilities.qwen, false]
  ];
  const list = document.querySelector('#health-list');
  list.replaceChildren();
  for (const [label, ready, required] of checks) {
    const row = document.createElement('div');
    row.className = 'health-row';
    const name = document.createElement('span');
    const state = document.createElement('strong');
    name.textContent = label + (required ? '' : '（按需）');
    state.textContent = ready ? '已就绪' : (required ? '需要安装' : '尚未安装');
    state.className = ready ? 'ready' : (required ? 'missing' : 'optional');
    row.append(name, state);
    list.append(row);
  }
  document.querySelector('#product-version').textContent = version ? `v${version}` : 'v1';
}

function renderJobs(jobs) {
  const list = document.querySelector('#jobs');
  list.replaceChildren();
  if (!jobs.length) {
    list.innerHTML = '<div class="empty-state">还没有运行记录</div>';
    return;
  }
  const statusNames = {running: '进行中', completed: '已完成', failed: '失败', interrupted: '已中断'};
  for (const item of jobs.slice(0, 6)) {
    const row = document.createElement('article');
    row.className = 'job';
    const head = document.createElement('div');
    head.className = 'job-head';
    const title = document.createElement('strong');
    title.textContent = item.label || item.id;
    const status = document.createElement('span');
    status.className = 'job-status ' + item.status;
    status.textContent = statusNames[item.status] || item.status;
    head.append(title, status);
    row.append(head);
    if (item.log_tail) {
      const log = document.createElement('pre');
      log.textContent = item.log_tail;
      row.append(log);
    }
    list.append(row);
  }
}

function renderStatistics(statistics = {}) {
  const values = [
    [statistics.runs || 0, '运行'],
    [statistics.projects || 0, '项目'],
    [statistics.completed || 0, '已完成'],
    [statistics.agent_tasks || 0, 'Agent 任务']
  ];
  const grid = document.querySelector('#statistics');
  grid.replaceChildren();
  for (const [value, label] of values) {
    const item = document.createElement('div');
    const strong = document.createElement('strong');
    const span = document.createElement('span');
    strong.textContent = value;
    span.textContent = label;
    item.append(strong, span);
    grid.append(item);
  }
  const formatCost = value => value > 0 && value < 0.0001 ? '<¥0.0001' : `¥${value.toFixed(4)}`;
  const minimum = Number(statistics.cost_cny_min || 0);
  const maximum = Number(statistics.cost_cny_max || 0);
  const costText = Math.abs(maximum - minimum) < 0.0000001
    ? formatCost(minimum)
    : `${formatCost(minimum)}～${formatCost(maximum)}`;
  document.querySelector('#cost-summary').textContent =
    `API 估算费用：${costText} · 价格更新 ${statistics.price_updated_at || '未知'}`;
  const projects = document.querySelector('#project-statistics');
  projects.replaceChildren();
  const rows = statistics.project_rows || [];
  if (!rows.length) {
    projects.innerHTML = '<div class="empty-inline">运行协作后会按项目自动汇总</div>';
    return;
  }
  for (const row of rows) {
    const item = document.createElement('div');
    item.className = 'project-stat-row';
    item.title = row.path;
    const head = document.createElement('div');
    head.className = 'project-stat-head';
    const name = document.createElement('strong');
    const detail = document.createElement('span');
    name.textContent = row.label;
    detail.textContent = `${row.runs} 次 · ${row.completed} 完成 · ${row.failed} 失败`;
    head.append(name, detail);
    item.append(head);
    for (const usage of row.models || []) {
      const model = document.createElement('div');
      model.className = 'model-usage';
      const modelName = document.createElement('strong');
      const tokenDetail = document.createElement('span');
      const priceDetail = document.createElement('span');
      modelName.textContent = `${providerNames[usage.provider] || usage.provider} · ${usage.model}`;
      if (usage.has_usage) {
        tokenDetail.textContent = `输入 ${Number(usage.input_tokens).toLocaleString()} · 缓存 ${Number(usage.cached_input_tokens).toLocaleString()} · 输出 ${Number(usage.output_tokens + usage.reasoning_tokens).toLocaleString()} Token`;
      } else if (usage.running) {
        tokenDetail.textContent = '正在调用，尚未返回 Token 数据';
      } else if (usage.pending) {
        tokenDetail.textContent = '等待执行或调用中，尚未返回 Token 数据';
      } else if (usage.failed) {
        tokenDetail.textContent = '调用失败，未产生 Token 数据';
      } else if (usage.completed) {
        tokenDetail.textContent = '调用完成，但 CLI 未返回 Token 数据';
      } else {
        tokenDetail.textContent = '暂无 Token 数据';
      }
      if (usage.cost) {
        priceDetail.textContent = Math.abs(usage.cost.max - usage.cost.min) < 0.0000001
          ? `估算 ${formatCost(usage.cost.min)}`
          : `峰谷估算 ${formatCost(usage.cost.min)}～${formatCost(usage.cost.max)}`;
      } else if (usage.billing === 'subscription') {
        priceDetail.textContent = '套餐/账号额度，不折算单次 API 费用';
      } else {
        priceDetail.textContent = '按量 API，当前模型价格未配置';
      }
      model.append(modelName, tokenDetail, priceDetail);
      item.append(model);
    }
    projects.append(item);
  }
}

async function refresh() {
  try {
    const data = await api('/api/snapshot');
    renderHealth(data.capabilities || {}, data.version || '');
    renderAccounts(data.accounts, data.capabilities || {}, data.preferences || {});
    if (!document.querySelector('#parallel').dataset.loaded) {
      document.querySelector('#parallel').value = data.preferences?.max_parallel_tasks || 2;
      document.querySelector('#parallel').dataset.loaded = 'true';
    }
    if (!document.querySelector('#routing-policy').dataset.loaded) {
      document.querySelector('#routing-policy').value = data.preferences?.routing_policy || 'balanced';
      document.querySelector('#routing-policy').dataset.loaded = 'true';
    }
    if (!document.querySelector('#timeout-minutes').dataset.loaded) {
      document.querySelector('#timeout-minutes').value = data.preferences?.timeout_minutes || 120;
      document.querySelector('#timeout-minutes').dataset.loaded = 'true';
    }
    renderJobs(data.jobs);
    renderStatistics(data.statistics || {});
    const running = data.jobs.some(item => item.status === 'running');
    clearTimeout(snapshotTimer);
    snapshotTimer = setTimeout(refresh, running ? 2000 : 7000);
  } catch (error) {
    console.error(error);
  }
}

document.querySelector('#master').addEventListener('change', async () => {
  const data = await api('/api/snapshot');
  renderAccounts(data.accounts, data.capabilities || {}, data.preferences || {});
});

document.querySelector('#login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const input = document.querySelector('#account-name');
  try {
    await api('/api/login', {
      method: 'POST',
      body: JSON.stringify({
        account: input.value,
        provider: document.querySelector('#agent-provider').value,
        model: document.querySelector('#agent-model').value,
        api_key: document.querySelector('#agent-key').value,
        device_auth: document.querySelector('#device-auth').checked
      })
    });
    input.value = '';
    document.querySelector('#agent-key').value = '';
    await refresh();
  } catch (error) {
    alert(error.message);
  }
});

document.querySelector('#run-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.submitter;
  const message = document.querySelector('#form-message');
  const workers = selectedWorkers();
  message.className = '';
  if (!workers.length) {
    message.textContent = '请至少选择一个执行 Agent';
    message.className = 'error';
    return;
  }
  button.disabled = true;
  message.textContent = '正在保存…';
  try {
    await api('/api/preferences', {
      method: 'POST',
      body: JSON.stringify({
        master_account: document.querySelector('#master').value,
        worker_agents: workers.map(id => {
          const agent = agentStates.get(id);
          return {id, provider: agent.provider, account: id, model: agent.model};
        }),
        max_parallel_tasks: document.querySelector('#parallel').value,
        routing_policy: document.querySelector('#routing-policy').value,
        timeout_minutes: document.querySelector('#timeout-minutes').value
      })
    });
    message.textContent = '协作配置已保存，可从项目对话调用';
    message.className = 'success';
    await refresh();
  } catch (error) {
    message.textContent = error.message;
    message.className = 'error';
  } finally {
    button.disabled = false;
  }
});

document.querySelector('#refresh').addEventListener('click', refresh);
function updateProviderFields() {
  const provider = document.querySelector('#agent-provider').value;
  const model = document.querySelector('#agent-model');
  const key = document.querySelector('#agent-key');
  const usesApiKey = Boolean(providerModels[provider]);
  document.querySelector('#device-option').hidden = provider !== 'codex';
  model.hidden = !usesApiKey;
  key.hidden = !usesApiKey;
  document.querySelector('#credential-note').hidden = !usesApiKey;
  if (providerModels[provider]) model.value = providerModels[provider];
  else model.value = '';
}
document.querySelector('#agent-provider').addEventListener('change', () => {
  document.querySelector('#agent-key').value = '';
  updateProviderFields();
});
updateProviderFields();
if (location.protocol === 'file:') {
  document.querySelector('#launch-guard').hidden = false;
} else {
  refresh();
}
