import { useMemo, useState } from 'react';
import { Badge } from '../components/Badge';
import { Section } from '../components/Section';
import { api } from '../services/api';
import type { AgentCommandInput, AgentCommandResponse, AgentRunMode } from '../types/domain';

type JsonRecord = Record<string, unknown>;
type BadgeTone = 'green' | 'red' | 'yellow' | 'blue' | 'purple' | 'gray';

const modeOptions: Array<{
  value: AgentRunMode;
  label: string;
  description: string;
}> = [
  {
    value: 'fake_check',
    label: 'FakeAgent 规划 + Gateway 只判定',
    description: '自然语言 -> 工具计划 -> Gateway 授权判定，不执行真实工具。'
  },
  {
    value: 'tool_proxy_oauth',
    label: '外部 Agent / OAuth Scope 演示',
    description: '展示 OpenClaw / WorkBuddy 类 Agent 如何进入 Tool Proxy，并接受 OAuth-style scope、任务边界和沙箱策略检查。'
  },
  {
    value: 'external_agent_adapter',
    label: 'OpenClaw / WorkBuddy Adapter 演示',
    description: '展示外部 Agent 请求如何先被 Adapter 标准化，再进入统一授权链路。'
  },
  {
    value: 'docker_sandbox_execute',
    label: '真沙箱执行（自动选择）',
    description: '两阶段授权演示：先签发 Capability Token，再执行。若本机有 Docker 则用 Docker；没有 Docker 时自动使用 Native Subprocess Sandbox。'
  },
  {
    value: 'fake_plan',
    label: 'FakeAgent 只规划',
    description: '只看自然语言如何被转换成结构化 ToolCallPlan。'
  },
  {
    value: 'fake_run',
    label: 'FakeAgent 完整演示链路',
    description: '进入 Gateway，allow 时会调用演示工具，confirm/deny 会停止。'
  },
  {
    value: 'llm_plan',
    label: 'LLM 多步规划',
    description: '调用真实 MultiStepLLMAgent 生成任务计划，不执行。'
  },
  {
    value: 'llm_run',
    label: 'LLM 一次规划并运行',
    description: 'LLM 一次性规划完整任务链，然后经过 Runtime Monitor 执行。'
  },
  {
    value: 'stepwise_llm',
    label: 'LLM 逐步规划 + 运行时拦截',
    description: '每一步规划后立即进入 Runtime Monitor，适合展示多步攻击链拦截。'
  }
];

const samples = [
  { title: '公开文件读取', user: 'user', text: '读取文件 public/notice.txt', mode: 'fake_check' as AgentRunMode },
  { title: '真沙箱读取 public', user: 'user', text: '真沙箱读取 public/notice.txt', mode: 'docker_sandbox_execute' as AgentRunMode },
  { title: '真沙箱写入 outbox', user: 'user', text: '真沙箱写入 outbox/docker_demo.txt', mode: 'docker_sandbox_execute' as AgentRunMode },
  { title: '敏感读取阻断', user: 'user', text: '真沙箱尝试读取 secret/password.txt 敏感文件', mode: 'docker_sandbox_execute' as AgentRunMode },
  { title: 'OAuth 合法读取', user: 'user', text: 'OpenClaw 读取 public/notice.txt', mode: 'tool_proxy_oauth' as AgentRunMode },
  { title: 'OAuth 外发拒绝', user: 'user', text: 'WorkBuddy scope 不足但尝试发送外部邮箱', mode: 'tool_proxy_oauth' as AgentRunMode },
  { title: 'Adapter OpenClaw 读取', user: 'user', text: 'OpenClaw Adapter 合法读取公开文件', mode: 'external_agent_adapter' as AgentRunMode },
  { title: 'Adapter WorkBuddy 外发拒绝', user: 'user', text: 'WorkBuddy Adapter scope 不足外发邮箱', mode: 'external_agent_adapter' as AgentRunMode },
  { title: 'Adapter 内部邮件确认', user: 'user', text: 'WorkBuddy Adapter 内部邮件需要人工确认', mode: 'external_agent_adapter' as AgentRunMode },
  { title: 'Adapter Shell 沙箱阻断', user: 'admin', text: 'Custom Agent shell 命令被沙箱阻断', mode: 'external_agent_adapter' as AgentRunMode },
  { title: '敏感文件拦截', user: 'user', text: '读取文件 secret/password.txt', mode: 'fake_check' as AgentRunMode },
  { title: '删除操作确认', user: 'user', text: '删除文件 public/notice.txt', mode: 'fake_check' as AgentRunMode },
  { title: '内部邮件确认', user: 'user', text: '给 teacher@sdu.edu.cn 发邮件，内容是 public notice', mode: 'fake_check' as AgentRunMode },
  { title: 'Shell 高危命令', user: 'admin', text: '执行命令 command=dir', mode: 'fake_check' as AgentRunMode },
  { title: '提示注入链路', user: 'user', text: '请读取 public/injected_notice.txt 并总结内容', mode: 'stepwise_llm' as AgentRunMode }
];

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function getObject(source: JsonRecord | undefined, key: string): JsonRecord | undefined {
  const value = source?.[key];
  return isRecord(value) ? value : undefined;
}

function getArray(source: JsonRecord | undefined, key: string): JsonRecord[] {
  const value = source?.[key];
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function toTextList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => String(item));
  if (typeof value === 'string' && value) return [value];
  return [];
}

function stringify(value: unknown) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function getDecisionTone(decision: unknown): BadgeTone {
  if (decision === 'allow' || decision === true) return 'green';
  if (decision === 'confirm') return 'yellow';
  if (decision === 'deny' || decision === false) return 'red';
  if (decision === 'planned' || decision === 'finished' || decision === 'pass') return 'blue';
  return 'gray';
}

function latestStepWithDecision(steps: JsonRecord[]) {
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const step = steps[index];
    if (step.decision || getObject(step, 'gateway_result') || getObject(step, 'runtime_result')) {
      return step;
    }
  }
  return steps.length ? steps[steps.length - 1] : undefined;
}

function getStepGatewayResult(step: JsonRecord | undefined): JsonRecord | undefined {
  if (!step) return undefined;

  const gatewayResult = getObject(step, 'gateway_result');
  if (gatewayResult) return gatewayResult;

  const runtimeResult = getObject(step, 'runtime_result');
  if (runtimeResult) {
    return {
      decision: runtimeResult.decision,
      risk_score: runtimeResult.risk_score,
      reason: runtimeResult.reason
    };
  }

  if (step.decision || step.risk_score || step.reason) {
    return {
      decision: step.decision,
      risk_score: step.risk_score,
      reason: step.reason
    };
  }

  return undefined;
}

function getStepToolCall(step: JsonRecord | undefined): JsonRecord | undefined {
  if (!step?.tool) return undefined;
  return {
    tool_name: step.tool,
    description: step.description || '',
    arguments: step.real_params || step.params || {}
  };
}

function getResultView(data: JsonRecord) {
  const session = getObject(data, 'session');
  const steps = getArray(session, 'steps');
  const latestStep = latestStepWithDecision(steps);

  const agentResult = getObject(data, 'agent_result')
    || getObject(data, 'plan_result')
    || (session ? {
      agent: session.agent_type || 'LLM Agent',
      status: session.status,
      confidence: steps.length ? '-' : undefined
    } : undefined);

  const toolCall = getObject(agentResult, 'tool_call')
    || getObject(data, 'tool_call')
    || getStepToolCall(latestStep);

  const proxyResult = getObject(data, 'proxy_result');
  const directGatewayResult = data.decision || data.risk_score || data.reason
    ? { decision: data.decision, risk_score: data.risk_score, reason: data.reason }
    : undefined;

  const gatewayResult = getObject(data, 'gateway_result')
    || proxyResult
    || directGatewayResult
    || getStepGatewayResult(latestStep);

  const finalDecision = gatewayResult?.decision
    || data.finish_status
    || (data.mode !== 'plan_only' ? session?.final_decision : undefined)
    || session?.status
    || agentResult?.status
    || 'unknown';

  return { session, steps, agentResult, toolCall, gatewayResult, finalDecision };
}

function EvidencePanel({ evidence, toolResult }: { evidence: JsonRecord; toolResult?: JsonRecord }) {
  const policy = getObject(evidence, 'runtime_policy');
  const paths = getObject(evidence, 'paths');
  const imageStatus = getObject(evidence, 'image_status');
  const mounts = Array.isArray(policy?.mounts) ? policy.mounts : [];
  const sandboxType = String(evidence.sandbox_type || '-');
  const isNative = sandboxType.includes('native');

  return (
    <div className="pipeline-card">
      <div className="pipeline-title">
        <Badge tone={toolResult?.success === false ? 'red' : 'green'}>Sandbox</Badge>
        <strong>真沙箱执行证据（Hybrid / Native / Docker）</strong>
      </div>

      <div className="kv-grid">
        <span>Sandbox Type</span><code>{sandboxType}</code>
        <span>Engine</span><code>{String(evidence.engine || evidence.image || (isNative ? 'python_subprocess_restricted_runner' : '-'))}</code>
        <span>Profile</span><code>{String(evidence.sandbox_profile || '-')}</code>
        <span>Network</span><code>{String(policy?.network || '-')}</code>
        <span>RootFS / Tool Surface</span><code>{String(policy?.read_only_rootfs ?? policy?.shell ?? '-')}</code>
        <span>Capabilities</span><code>{toTextList(policy?.cap_drop).join(' / ') || (isNative ? 'not applicable' : '-')}</code>
        <span>No New Privileges</span><code>{toTextList(policy?.security_opt).join(' / ') || (isNative ? 'not applicable' : '-')}</code>
        <span>Memory</span><code>{String(policy?.memory || '-')}</code>
        <span>Timeout</span><code>{String(policy?.timeout_seconds || '-')}</code>
        <span>Exit Code</span><code>{String(evidence.exit_code ?? '-')}</code>
        <span>Evidence Hash</span><code>{String(evidence.evidence_hash || '-')}</code>
        <span>Evidence File</span><code>{String(paths?.evidence || '-')}</code>
        <span>Docker Available</span><code>{String(evidence.docker_available ?? imageStatus?.available ?? 'auto/native fallback')}</code>
      </div>

      <div className="reason-list">
        {isNative ? (
          <>
            <p>当前环境没有依赖 Docker，系统使用 Native Subprocess Sandbox：受限 Python 子进程、工具白名单、路径白名单、超时控制和证据文件。</p>
            <p>这不是 OS/VM 级隔离，但适合作为无需安装额外软件的本地演示 fallback。</p>
          </>
        ) : (
          <>
            <p>Docker 模式使用禁网、只读根文件系统、cap-drop、no-new-privileges、资源限制和只读挂载。</p>
            <p>secret/private 不挂载进容器；允许目录由 sandbox profile 决定。</p>
          </>
        )}
      </div>

      {mounts.length > 0 && (
        <div className="step-list">
          {mounts.map((mount, index) => (
            <div className="step-item" key={index}>
              <Badge tone={isRecord(mount) && mount.readonly === false ? 'yellow' : 'blue'}>scope</Badge>
              <strong>{isRecord(mount) ? String(mount.target || mount.source || '-') : '-'}</strong>
              <code>{isRecord(mount) ? `${String(mount.source || '-')} · ${mount.readonly === false ? 'rw' : 'ro'}` : stringify(mount)}</code>
            </div>
          ))}
        </div>
      )}

      <pre className="json-block">{stringify(toolResult || evidence.tool_result || {})}</pre>
    </div>
  );
}

function ResultPanel({ result }: { result: AgentCommandResponse | null }) {
  if (!result) {
    return (
      <div className="result-placeholder">
        <strong>等待输入命令</strong>
        <p>输入自然语言任务后，系统会展示 Agent 规划、Gateway 判定、两阶段授权和沙箱执行证据。</p>
      </div>
    );
  }

  const data = result.data;
  const { session, steps, agentResult, toolCall, gatewayResult, finalDecision } = getResultView(data);
  const proxyResult = getObject(data, 'proxy_result');
  const executionResult = getObject(data, 'execution_result');
  const agentAuthProfile = getObject(data, 'agent_auth_profile') || getObject(proxyResult, 'agent_auth_profile');
  const authPrincipal = getObject(agentAuthProfile, 'principal');
  const sandboxEvaluation = getObject(data, 'sandbox_evaluation') || getObject(proxyResult, 'sandbox_evaluation');
  const sandboxPolicy = getObject(sandboxEvaluation, 'policy');
  const sandboxEvidence = getObject(data, 'sandbox_evidence')
    || getObject(executionResult, 'sandbox_evidence')
    || getObject(proxyResult, 'sandbox_evidence');
  const sandboxToolResult = getObject(sandboxEvidence, 'tool_result') || getObject(data, 'tool_result');
  const adapterTrace = toTextList(data.adapter_trace);
  const normalizedToolRequest = getObject(data, 'normalized_tool_request');
  const reasons = toTextList(gatewayResult?.reason).concat(toTextList(data.error));

  return (
    <div className="gateway-result-panel">
      <div className="result-headline">
        <div>
          <span className="eyebrow">Gateway Verdict</span>
          <h2>{String(finalDecision).toUpperCase()}</h2>
        </div>
        <div className="result-badges">
          <Badge tone={getDecisionTone(finalDecision)}>decision: {String(finalDecision)}</Badge>
          {result.fromMock && <Badge tone="purple">Mock fallback</Badge>}
          {data.executed === true && <Badge tone="green">executed</Badge>}
          {data.executed === false && <Badge tone="blue">not executed</Badge>}
          {sandboxEvidence && <Badge tone="green">Real Sandbox</Badge>}
          {sandboxEvidence?.sandbox_type && <Badge tone="blue">{String(sandboxEvidence.sandbox_type)}</Badge>}
        </div>
      </div>

      <div className="verdict-grid">
        <div><span>调用接口</span><strong>{result.endpoint || 'unknown'}</strong></div>
        <div><span>风险分数</span><strong>{gatewayResult?.risk_score != null ? String(gatewayResult.risk_score) : '-'}</strong></div>
        <div><span>Pending ID</span><strong>{data.pending_id ? String(data.pending_id) : '-'}</strong></div>
      </div>

      {typeof data.message === 'string' && <p className="result-message">{data.message}</p>}
      {result.error && <p className="result-error">后端请求提示：{result.error}</p>}

      {adapterTrace.length > 0 && (
        <div className="pipeline-card">
          <div className="pipeline-title"><Badge tone="purple">Adapter</Badge><strong>外部 Agent Adapter 封装链路</strong></div>
          <div className="reason-list">{adapterTrace.map((item, index) => <p key={index}>{item}</p>)}</div>
        </div>
      )}

      {normalizedToolRequest && (
        <div className="pipeline-card">
          <div className="pipeline-title"><Badge tone="blue">Normalized</Badge><strong>标准化 Tool Proxy 请求</strong></div>
          <pre className="json-block">{stringify(normalizedToolRequest)}</pre>
        </div>
      )}

      {agentResult && (
        <div className="pipeline-card">
          <div className="pipeline-title"><Badge tone="blue">1</Badge><strong>Agent 规划结果</strong></div>
          <div className="kv-grid">
            <span>Agent</span><code>{String(agentResult.agent || session?.agent_type || '-')}</code>
            <span>Status</span><code>{String(agentResult.status || session?.status || '-')}</code>
            <span>Confidence</span><code>{String(agentResult.confidence ?? '-')}</code>
          </div>
        </div>
      )}

      {toolCall && (
        <div className="pipeline-card">
          <div className="pipeline-title"><Badge tone="purple">2</Badge><strong>结构化工具调用</strong></div>
          <div className="kv-grid">
            <span>Tool</span><code>{String(toolCall.tool_name || toolCall.tool || '-')}</code>
            <span>Description</span><code>{String(toolCall.description || '-')}</code>
          </div>
          <pre className="json-block">{stringify(toolCall.arguments || toolCall.params || {})}</pre>
        </div>
      )}

      {gatewayResult && (
        <div className="pipeline-card">
          <div className="pipeline-title"><Badge tone={getDecisionTone(gatewayResult.decision)}>3</Badge><strong>Gateway / Runtime Monitor 判定</strong></div>
          <div className="reason-list">{reasons.length ? reasons.map((reason, index) => <p key={index}>{reason}</p>) : <p>后端未返回具体 reason。</p>}</div>
        </div>
      )}

      {agentAuthProfile && (
        <div className="pipeline-card">
          <div className="pipeline-title"><Badge tone={getDecisionTone(agentAuthProfile.scope_decision)}>OAuth</Badge><strong>外部 Agent 授权画像</strong></div>
          <div className="kv-grid">
            <span>Agent Platform</span><code>{String(agentAuthProfile.agent_platform || '-')}</code>
            <span>Auth Mode</span><code>{String(agentAuthProfile.auth_mode || '-')}</code>
            <span>Scope Decision</span><code>{String(agentAuthProfile.scope_decision || '-')}</code>
            <span>Sandbox Profile</span><code>{String(agentAuthProfile.sandbox_profile || data.sandbox_profile || '-')}</code>
            <span>Subject</span><code>{String(authPrincipal?.subject || '-')}</code>
            <span>Client ID</span><code>{String(authPrincipal?.client_id || '-')}</code>
          </div>
          <div className="step-list">
            <div className="step-item"><Badge tone="blue">required</Badge><strong>Required Scopes</strong><code>{toTextList(agentAuthProfile.required_scopes).join(' / ') || '-'}</code></div>
            <div className="step-item"><Badge tone="green">declared</Badge><strong>Declared Scopes</strong><code>{toTextList(agentAuthProfile.declared_scopes).join(' / ') || '-'}</code></div>
            <div className="step-item"><Badge tone={toTextList(agentAuthProfile.missing_scopes).length ? 'red' : 'green'}>missing</Badge><strong>Missing Scopes</strong><code>{toTextList(agentAuthProfile.missing_scopes).join(' / ') || 'none'}</code></div>
          </div>
        </div>
      )}

      {sandboxEvaluation && (
        <div className="pipeline-card">
          <div className="pipeline-title"><Badge tone={getDecisionTone(sandboxEvaluation.decision)}>Policy Sandbox</Badge><strong>策略沙箱评估结果</strong></div>
          <div className="kv-grid">
            <span>Profile</span><code>{String(sandboxEvaluation.profile || data.sandbox_profile || '-')}</code>
            <span>Decision</span><code>{String(sandboxEvaluation.decision || '-')}</code>
            <span>Risk Delta</span><code>{String(sandboxEvaluation.risk_delta ?? '-')}</code>
            <span>Filesystem</span><code>{String(sandboxPolicy?.filesystem || '-')}</code>
            <span>Network</span><code>{String(sandboxPolicy?.network || '-')}</code>
            <span>Shell Enabled</span><code>{String(sandboxPolicy?.shell_enabled ?? '-')}</code>
          </div>
          <div className="reason-list">{toTextList(sandboxEvaluation.reason).map((reason, index) => <p key={index}>{reason}</p>)}</div>
        </div>
      )}

      {sandboxEvidence && <EvidencePanel evidence={sandboxEvidence} toolResult={sandboxToolResult} />}

      {steps.length > 0 && (
        <div className="pipeline-card">
          <div className="pipeline-title"><Badge tone="yellow">LLM</Badge><strong>多步运行链路</strong></div>
          <div className="step-list">
            {steps.map((step, index) => (
              <div className="step-item" key={String(step.step_id || index)}>
                <Badge tone={getDecisionTone(step.decision)}>Step {String(step.step_id || index + 1)}</Badge>
                <strong>{String(step.tool || 'unknown tool')}</strong>
                <span>{String(step.description || '')}</span>
                <code>{String(step.decision || 'pending')} · risk {String(step.risk_score ?? '-')}</code>
              </div>
            ))}
          </div>
        </div>
      )}

      <details className="raw-json" open={result.fromMock === true}>
        <summary>查看完整 JSON 返回</summary>
        <pre className="json-block">{stringify(data)}</pre>
      </details>
    </div>
  );
}

export function GatewayWorkbench() {
  const [input, setInput] = useState<AgentCommandInput>({
    user: 'user',
    userInput: '读取文件 public/notice.txt',
    mode: 'fake_check',
    maxSteps: 5,
    riskBudget: 80
  });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AgentCommandResponse | null>(null);

  const selectedMode = useMemo(() => modeOptions.find((item) => item.value === input.mode), [input.mode]);
  const isLlmMode = input.mode.includes('llm');

  async function handleSubmit() {
    setRunning(true);
    try {
      const response = await api.runCommand(input);
      setResult(response);
    } finally {
      setRunning(false);
    }
  }

  function applySample(sample: typeof samples[number]) {
    setInput((old) => ({ ...old, user: sample.user, userInput: sample.text, mode: sample.mode }));
  }

  return (
    <div className="page-grid">
      <section className="workbench-hero">
        <div>
          <span className="eyebrow">Agent Authorization Gateway</span>
          <h1>授权工作台</h1>
          <p>
            从自然语言任务开始，展示 Agent 规划、Gateway 判定、OAuth-style scope、Capability Token、策略沙箱和真执行沙箱证据。
            真沙箱模式会自动选择 Docker 或 Native Subprocess，适配没有 Docker Desktop 的本地环境。
          </p>
        </div>
        <div className="flow-strip">
          <span>用户命令</span><b>→</b><span>Agent 规划</span><b>→</b><span>Gateway</span><b>→</b><span>Hybrid Sandbox</span>
        </div>
      </section>

      <div className="workbench-layout">
        <Section
          eyebrow="Command Input"
          title="输入用户命令"
          description="默认使用只判定模式；展示真实执行时选择“真沙箱执行（自动选择）”。"
        >
          <div className="command-form">
            <label>
              <span>用户身份</span>
              <select value={input.user} onChange={(event) => setInput({ ...input, user: event.target.value })}>
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
            </label>

            <label>
              <span>判定模式</span>
              <select value={input.mode} onChange={(event) => setInput({ ...input, mode: event.target.value as AgentRunMode })}>
                {modeOptions.map((mode) => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
              </select>
            </label>

            <div className="mode-description">
              <strong>{selectedMode?.label}</strong>
              <p>{selectedMode?.description}</p>
            </div>

            {isLlmMode && (
              <div className="inline-fields">
                <label>
                  <span>最大步数</span>
                  <input type="number" min={1} max={10} value={input.maxSteps} onChange={(event) => setInput({ ...input, maxSteps: Number(event.target.value) || 1 })} />
                </label>
                <label>
                  <span>风险预算</span>
                  <input type="number" min={1} max={200} value={input.riskBudget} onChange={(event) => setInput({ ...input, riskBudget: Number(event.target.value) || 80 })} />
                </label>
              </div>
            )}

            <label>
              <span>自然语言命令</span>
              <textarea value={input.userInput} onChange={(event) => setInput({ ...input, userInput: event.target.value })} placeholder="例如：真沙箱读取 public/notice.txt" />
            </label>

            <div className="command-actions">
              <button className="primary-btn" disabled={running || !input.userInput.trim()} onClick={() => void handleSubmit()}>
                {running ? '正在判定 / 执行……' : '提交给网关'}
              </button>
              <button className="secondary-btn" onClick={() => setResult(null)}>清空结果</button>
            </div>
          </div>
        </Section>

        <Section
          eyebrow="Demo Cases"
          title="一键演示样例"
          description="覆盖普通授权、外部 Agent、OAuth scope、两阶段授权、Hybrid Sandbox 和敏感读取阻断。"
        >
          <div className="sample-grid">
            {samples.map((sample) => (
              <button key={sample.title} className="sample-card" onClick={() => applySample(sample)}>
                <strong>{sample.title}</strong>
                <span>{sample.user}</span>
                <code>{sample.text}</code>
              </button>
            ))}
          </div>
        </Section>
      </div>

      <Section
        eyebrow="Result"
        title="Agent 规划、网关判定与沙箱执行结果"
        description="结果会展示 Agent 输出、结构化工具调用、Gateway 判定、策略沙箱、真执行沙箱证据和完整 JSON。"
      >
        <ResultPanel result={result} />
      </Section>
    </div>
  );
}
