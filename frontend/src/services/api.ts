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
const REQUEST_TIMEOUT_MS = 2800;
const COMMAND_TIMEOUT_MS = 20000;

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
        'Content-Type': 'application/json',
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
      headers: { 'Content-Type': 'application/json' },
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
  const isDelete = input.userInput.includes('鍒犻櫎') || lowered.includes('delete') || lowered.includes('remove');
  const isShell = input.userInput.includes('鍛戒护') || lowered.includes('shell') || lowered.includes('command');
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
      message: '鍚庣鏈繛鎺ワ紝褰撳墠灞曠ず鐨勬槸鍓嶇 Mock 鍒ゅ畾銆傚惎鍔ㄥ悗绔悗浼氳嚜鍔ㄨ皟鐢ㄧ湡瀹?FakeAgent / LLM 鎺ュ彛銆?,
      original_input: input.userInput,
      agent_result: {
        agent: input.mode.includes('llm') ? 'MultiStepLLMAgent' : 'FakeAgent',
        status: isUnknown ? 'unsupported' : 'planned',
        confidence: isUnknown ? 0 : 0.88,
        original_input: input.userInput,
        tool_call: isUnknown ? null : {
          tool_name: isShell ? 'shell.run' : isDelete ? 'file.delete' : 'file.read',
          description: isShell ? '鎵ц绯荤粺鍛戒护' : isDelete ? '鍒犻櫎鏂囦欢' : '璇诲彇鏂囦欢鍐呭',
          arguments: isShell
            ? { command: input.userInput }
            : { path: isSecret ? 'secret/password.txt' : isDelete ? 'public/notice.txt' : 'public/notice.txt' },
          need_auth: true
        }
      },
      gateway_result: {
        decision,
        risk_score: riskScore,
        reason: decision === 'allow'
          ? ['Mock锛氬叕寮€璧勬簮璇诲彇锛岄闄╄緝浣庛€?]
          : decision === 'confirm'
            ? ['Mock锛氬垹闄ょ被鎿嶄綔鍏锋湁鐮村潖鎬э紝闇€瑕佷汉宸ョ‘璁ゃ€?]
            : ['Mock锛氬懡涓晱鎰熻矾寰勩€佺郴缁熷懡浠ゆ垨涓嶅彲璇嗗埆浠诲姟锛岀姝㈡墽琛屻€?]
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
        message: 'FakeAgent 鏈敓鎴愬彲鎵ц宸ュ叿璋冪敤锛屽洜姝ゆ湭杩涘叆 Gateway 鍒ゅ畾銆?,
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
    tool: toolCall.tool_name,
    params: toolCall.arguments || {},
    agent_confidence: agentResult.confidence,
    plan_status: agentResult.status
  });

  return {
    ok: true,
    endpoint: `${planEndpoint} -> ${checkEndpoint}`,
    data: {
      success: true,
      executed: false,
      source: 'frontend.fake_check',
      message: 'FakeAgent 宸插畬鎴愯嚜鐒惰瑷€瑙勫垝锛孏ateway 宸插畬鎴愭巿鏉冨垽瀹氾紝鏈墽琛岀湡瀹炲伐鍏枫€?,
      original_input: input.userInput,
      agent_result: agentResult,
      gateway_result: gatewayResult,
      tool_result: null,
      pending_id: null
    }
  };
}

async function runCommand(input: AgentCommandInput): Promise<AgentCommandResponse> {
  try {
    if (input.mode === 'fake_check') {
      return await runFakeAgentCheck(input);
    }

    const endpointMap: Record<Exclude<AgentCommandInput['mode'], 'fake_check'>, string> = {
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
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision })
      });
    } catch {
      // Mock 妯″紡涓嬫棤闇€鐪熷疄鎻愪氦銆?    }
  }
};

