import type {
  AgentCommandInput,
  AgentCommandResponse,
  AuditLog,
  EvaluationMetric,
  GatewayRequest,
  Overview,
  PolicyRule,
  SystemSetting
} from '../types/domain';
import * as mock from './mockData';

const API_BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');
const REQUEST_TIMEOUT_MS = 30000;
const COMMAND_TIMEOUT_MS = 60000;

type MockKey = 'overview' | 'requests' | 'policies' | 'auditLogs' | 'evaluations' | 'settings';

const mockMap: Record<MockKey, unknown> = {
  overview: mock.overview,
  requests: mock.requests,
  policies: mock.policies,
  auditLogs: mock.auditLogs,
  evaluations: mock.evaluations,
  settings: mock.settings
};

function buildUrl(endpoint: string) {
  if (!API_BASE) return endpoint;
  return `${API_BASE}${endpoint}`;
}

async function request<T>(endpoint: string, mockKey: MockKey, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(buildUrl(endpoint), {
      ...init,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        ...(init?.headers || {})
      },
      signal: controller.signal
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } catch {
    return mockMap[mockKey] as T;
  } finally {
    window.clearTimeout(timer);
  }
}

async function postJson(endpoint: string, body: unknown, timeoutMs = COMMAND_TIMEOUT_MS): Promise<Record<string, unknown>> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(buildUrl(endpoint), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify(body),
      signal: controller.signal
    });

    const contentType = res.headers.get('content-type') || '';
    const payload = contentType.includes('application/json')
      ? await res.json()
      : { message: await res.text() };

    if (!res.ok) {
      const message = typeof payload?.detail === 'string'
        ? payload.detail
        : `HTTP ${res.status}`;
      throw new Error(message);
    }

    return payload as Record<string, unknown>;
  } finally {
    window.clearTimeout(timer);
  }
}

function mockCommandResponse(input: AgentCommandInput, error?: unknown): AgentCommandResponse {
  const lowered = input.userInput.toLowerCase();
  const isSecret = input.userInput.includes('secret/') || input.userInput.includes('password');
  const isDelete = input.userInput.includes('删除') || lowered.includes('delete') || lowered.includes('remove');
  const isShell = input.userInput.includes('命令') || lowered.includes('shell') || lowered.includes('command');
  const isUnknown = !input.userInput.trim();

  const decision = isUnknown ? 'deny' : isSecret || isShell ? 'deny' : isDelete ? 'confirm' : 'allow';
  const riskScore = decision === 'deny' ? 92 : decision === 'confirm' ? 68 : 18;

  return {
    ok: false,
    fromMock: true,
    error: error instanceof Error ? error.message : 'Backend unavailable, using frontend mock result.',
    endpoint: 'mock://agent-command',
    data: {
      success: true,
      executed: false,
      source: 'frontend.mock',
      message: '后端未连接，当前展示的是前端 Mock 判定。启动后端后会自动调用真实 FakeAgent / LLM 接口。',
      original_input: input.userInput,
      agent_result: {
        agent: input.mode.includes('llm') ? 'MultiStepLLMAgent' : 'FakeAgent',
        status: isUnknown ? 'unsupported' : 'planned',
        confidence: isUnknown ? 0 : 0.88,
        original_input: input.userInput,
        tool_call: isUnknown ? null : {
          tool_name: isShell ? 'shell.run' : isDelete ? 'file.delete' : 'file.read',
          description: isShell ? '执行系统命令' : isDelete ? '删除文件' : '读取文件内容',
          arguments: isShell
            ? { command: input.userInput }
            : { path: isSecret ? 'secret/password.txt' : 'public/notice.txt' },
          need_auth: true
        }
      },
      gateway_result: {
        decision,
        risk_score: riskScore,
        reason: decision === 'allow'
          ? ['Mock：公开资源读取，风险较低。']
          : decision === 'confirm'
            ? ['Mock：删除类操作具有破坏性，需要人工确认。']
            : ['Mock：命中敏感路径、系统命令或不可识别任务，禁止执行。']
      },
      tool_result: null,
      pending_id: decision === 'confirm' ? 'mock-pending-001' : null
    }
  };
}

function getToolCallFromAgentResult(agentResult: Record<string, unknown>) {
  const toolCall = agentResult.tool_call;
  if (!toolCall || typeof toolCall !== 'object') return null;
  return toolCall as Record<string, unknown>;
}

async function runFakeAgentCheck(input: AgentCommandInput): Promise<AgentCommandResponse> {
  const planEndpoint = '/demo/fake-agent/plan';
  const planResponse = await postJson(planEndpoint, {
    user: input.user,
    user_input: input.userInput
  });

  const agentResult = (planResponse.agent_result || {}) as Record<string, unknown>;
  const toolCall = getToolCallFromAgentResult(agentResult);

  if (!toolCall) {
    return {
      ok: true,
      endpoint: `${planEndpoint} -> no gateway check`,
      data: {
        success: true,
        executed: false,
        source: 'frontend.fake_check',
        message: 'FakeAgent 未生成可执行工具调用，因此未进入 Gateway 判定。',
        original_input: input.userInput,
        agent_result: agentResult,
        gateway_result: null,
        tool_result: null,
        pending_id: null
      }
    };
  }

  const checkEndpoint = '/gateway/check';
  const gatewayResult = await postJson(checkEndpoint, {
    user: input.user,
    tool: toolCall.tool_name || toolCall.tool,
    params: toolCall.arguments || toolCall.params || {},
    agent_confidence: agentResult.confidence,
    plan_status: agentResult.status,
    original_input: input.userInput
  });

  return {
    ok: true,
    endpoint: `${planEndpoint} -> ${checkEndpoint}`,
    data: {
      success: true,
      executed: false,
      source: 'frontend.fake_check',
      message: 'FakeAgent 已完成自然语言规划，Gateway 已完成授权判定，未执行真实工具。',
      original_input: input.userInput,
      agent_result: agentResult,
      gateway_result: gatewayResult,
      tool_result: null,
      pending_id: null
    }
  };
}

async function runToolProxyOAuthDemo(input: AgentCommandInput): Promise<AgentCommandResponse> {
  const endpoint = '/tool-proxy/authorize';
  const lowered = input.userInput.toLowerCase();
  const isExternalSend =
    input.userInput.includes('外发')
    || input.userInput.includes('发送')
    || input.userInput.includes('邮箱')
    || lowered.includes('email')
    || lowered.includes('workbuddy');

  const body = isExternalSend
    ? {
        user: input.user,
        original_task: '请把内容发送给外部邮箱',
        tool: 'email.send',
        params: {
          to: 'attacker@example.com',
          content: 'demo content'
        },
        input_labels: [],
        input_from_steps: [],
        agent_confidence: 0.95,
        execute: false,
        agent_platform: 'workbuddy',
        auth_mode: 'oauth_scope',
        requested_scopes: ['tool:file:read'],
        oauth_token_claims: {
          sub: 'agent-workbuddy-demo',
          client_id: 'workbuddy-demo-client',
          scope: 'tool:file:read'
        },
        sandbox_profile: 'strict',
        external_agent_metadata: {
          demo_case: 'insufficient_scope_external_email'
        }
      }
    : {
        user: input.user,
        original_task: '请读取 public/notice.txt 并总结',
        tool: 'file.read',
        params: {
          path: 'public/notice.txt'
        },
        input_labels: [],
        input_from_steps: [],
        agent_confidence: 0.95,
        execute: false,
        agent_platform: 'openclaw',
        auth_mode: 'oauth_scope',
        requested_scopes: ['tool:file:read'],
        oauth_token_claims: {
          sub: 'agent-openclaw-demo',
          client_id: 'openclaw-demo-client',
          scope: 'tool:file:read'
        },
        sandbox_profile: 'local_readonly',
        external_agent_metadata: {
          demo_case: 'valid_scope_public_read'
        }
      };

  const data = await postJson(endpoint, body);

  return {
    ok: true,
    endpoint,
    data: {
      ...data,
      source: 'frontend.tool_proxy_oauth',
      message: isExternalSend
        ? 'WorkBuddy 只声明 tool:file:read，却尝试 email.send，Tool Proxy 在 OAuth-style scope 检查阶段拒绝。'
        : 'OpenClaw 声明 tool:file:read，并读取公开文件，Tool Proxy scope 检查通过后继续进入 Runtime Monitor。'
    }
  };
}


async function runExternalAgentAdapterDemo(input: AgentCommandInput): Promise<AgentCommandResponse> {
  const endpoint = '/external-agent/simulate';
  const lowered = input.userInput.toLowerCase();

  let platform = 'openclaw';
  let scenario = 'valid_public_read';
  let user = input.user;

  if (
    input.userInput.includes('外发')
    || input.userInput.includes('scope 不足')
    || input.userInput.includes('Scope 不足')
    || input.userInput.includes('邮箱')
    || lowered.includes('insufficient')
    || lowered.includes('workbuddy')
  ) {
    platform = 'workbuddy';
    scenario = 'insufficient_scope_email';
  }

  if (
    input.userInput.includes('内部邮件')
    || input.userInput.includes('人工确认')
    || lowered.includes('confirm')
  ) {
    platform = 'workbuddy';
    scenario = 'valid_internal_email_confirm';
  }

  if (
    input.userInput.includes('shell')
    || input.userInput.includes('命令')
    || input.userInput.includes('沙箱')
    || lowered.includes('sandbox')
  ) {
    platform = 'custom';
    scenario = 'sandbox_block_shell';
    user = 'admin';
  }

  const data = await postJson(endpoint, {
    platform,
    scenario,
    user,
    execute: false
  });

  return {
    ok: true,
    endpoint,
    data: {
      ...data,
      source: 'frontend.external_agent_adapter',
      message: '外部 Agent 请求已先进入 Adapter 标准化，再进入 Tool Proxy、OAuth-style scope、Capability Contract 和 Runtime Monitor。'
    }
  };
}

async function runCommand(input: AgentCommandInput): Promise<AgentCommandResponse> {
  try {
    if (input.mode === 'fake_check') {
      return await runFakeAgentCheck(input);
    }

    if (input.mode === 'tool_proxy_oauth') {
      return await runToolProxyOAuthDemo(input);
    }

    if (input.mode === 'external_agent_adapter') {
      return await runExternalAgentAdapterDemo(input);
    }

    const endpointMap: Record<Exclude<AgentCommandInput['mode'], 'fake_check' | 'tool_proxy_oauth' | 'external_agent_adapter'>, string> = {
      fake_plan: '/demo/fake-agent/plan',
      fake_run: '/demo/fake-agent/run',
      llm_plan: '/agent-runtime/multistep-llm/plan',
      llm_run: '/agent-runtime/multistep-llm/run',
      stepwise_llm: '/agent-runtime/stepwise-llm/run'
    };

    const endpoint = endpointMap[input.mode];
    const body = input.mode.includes('llm')
      ? {
          user: input.user,
          user_input: input.userInput,
          max_steps: input.maxSteps,
          risk_budget: input.riskBudget
        }
      : {
          user: input.user,
          user_input: input.userInput
        };

    const data = await postJson(endpoint, body);
    return { ok: true, endpoint, data };
  } catch (error) {
    return mockCommandResponse(input, error);
  }
}

export const api = {
  getOverview: () => request<Overview>('/api/overview', 'overview'),
  getRequests: () => request<GatewayRequest[]>('/api/requests', 'requests'),
  getPolicies: () => request<PolicyRule[]>('/api/policies', 'policies'),
  getAuditLogs: () => request<AuditLog[]>('/api/audit-logs', 'auditLogs'),
  getEvaluations: () => request<EvaluationMetric[]>('/api/evaluations', 'evaluations'),
  getSettings: () => request<SystemSetting[]>('/api/settings', 'settings'),
  runCommand,
  submitDecision: async (id: string, decision: 'approved' | 'rejected') => {
    try {
      await fetch(buildUrl(`/api/requests/${id}/decision`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json; charset=utf-8'
        },
        body: JSON.stringify({ decision })
      });
    } catch {
      // Mock 模式下无需真实提交。
    }
  }
};
