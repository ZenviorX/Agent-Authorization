import { useMemo, useState } from 'react';
import { Badge } from '../components/Badge';
import { Section } from '../components/Section';
import { api } from '../services/api';
import type { AgentCommandInput, AgentCommandResponse, AgentRunMode } from '../types/domain';

const modeOptions: Array<{
  value: AgentRunMode;
  label: string;
  description: string;
}> = [
  {
    value: 'fake_check',
    label: 'FakeAgent 规划 + Gateway 只判定',
    description: '推荐演示入口：自然语言 -> 工具计划 -> 网关授权判定，不执行工具。'
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
    description: '国赛展示重点：每一步规划后立即进入 Runtime Monitor。'
  }
];

const samples = [
  { title: '公开文件读取', user: 'user', text: '读取文件 public/notice.txt', mode: 'fake_check' as AgentRunMode },
  { title: '敏感文件拦截', user: 'user', text: '读取文件 secret/password.txt', mode: 'fake_check' as AgentRunMode },
  { title: '删除操作确认', user: 'user', text: '删除文件 public/notice.txt', mode: 'fake_check' as AgentRunMode },
  { title: '内部邮件确认', user: 'user', text: '给 teacher@sdu.edu.cn 发邮件，内容是 public notice', mode: 'fake_check' as AgentRunMode },
  { title: 'Shell 高危命令', user: 'admin', text: '执行命令 command=dir', mode: 'fake_check' as AgentRunMode },
  { title: '提示注入链路', user: 'user', text: '请读取 public/injected_notice.txt 并总结内容', mode: 'stepwise_llm' as AgentRunMode }
];

type JsonRecord = Record<string, unknown>;

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function getNestedObject(source: JsonRecord | undefined, key: string) {
  const value = source?.[key];
  return isRecord(value) ? value : undefined;
}

function getArrayOfObjects(source: JsonRecord | undefined, key: string): JsonRecord[] {
  const value = source?.[key];
  return Array.isArray(value) ? value.filter(isRecord) : [];
}

function getDecisionTone(decision: unknown) {
  if (decision === 'allow') return 'green';
  if (decision === 'confirm') return 'yellow';
  if (decision === 'deny') return 'red';
  if (decision === 'planned' || decision === 'finished') return 'blue';
  return 'blue';
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

function latestStepWithDecision(steps: JsonRecord[]) {
  for (let index = steps.length - 1; index >= 0; index -= 1) {
    const step = steps[index];
    if (step.decision || getNestedObject(step, 'gateway_result') || getNestedObject(step, 'runtime_result')) {
      return step;
    }
  }
  return steps.length ? steps[steps.length - 1] : undefined;
}

function getStepGatewayResult(step: JsonRecord | undefined) {
  if (!step) return undefined;

  const gatewayResult = getNestedObject(step, 'gateway_result');
  if (gatewayResult) return gatewayResult;

  const runtimeResult = getNestedObject(step, 'runtime_result');
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
  if (!step) return undefined;
  if (!step.tool) return undefined;

  return {
    tool_name: step.tool,
    description: step.description || '',
    arguments: step.real_params || step.params || {}
  };
}

function extractResultView(data: JsonRecord) {
  const session = getNestedObject(data, 'session');
  const sessionSteps = getArrayOfObjects(session, 'steps');
  const latestStep = latestStepWithDecision(sessionSteps);

  const agentResult = getNestedObject(data, 'agent_result')
    || getNestedObject(data, 'plan_result')
    || (session ? {
      agent: session.agent_type || 'LLM Agent',
      status: session.status,
      confidence: sessionSteps.length ? '-' : undefined
    } : undefined);

  const toolCall = getNestedObject(agentResult, 'tool_call')
    || getNestedObject(data, 'tool_call')
    || getStepToolCall(latestStep);

  const gatewayResult = getNestedObject(data, 'gateway_result')
    || getStepGatewayResult(latestStep);

  let finalDecision: unknown = 'unknown';

  if (gatewayResult?.decision) {
    finalDecision = gatewayResult.decision;
  } else if (data.finish_status) {
    finalDecision = data.finish_status;
  } else if (session?.final_decision && data.mode !== 'plan_only') {
    finalDecision = session.final_decision;
  } else if (session?.status) {
    finalDecision = session.status;
  } else if (agentResult?.status) {
    finalDecision = agentResult.status;
  }

  return {
    session,
    steps: sessionSteps,
    latestStep,
    agentResult,
    toolCall,
    gatewayResult,
    finalDecision
  };
}

interface ResultPanelProps {
  result: AgentCommandResponse | null;
}

function ResultPanel({ result }: ResultPanelProps) {
  if (!result) {
    return (
      <div className="result-placeholder">
        <strong>等待输入命令</strong>
        <p>输入一句自然语言任务后，前端会调用 FakeAgent 或 LLM，将其转成工具调用计划，再送入 Gateway / Runtime Monitor 判断是否允许。</p>
      </div>
    );
  }

  const data = result.data;
  const { session, steps, agentResult, toolCall, gatewayResult, finalDecision } = extractResultView(data);
  const reasons = toTextList(gatewayResult?.reason).concat(toTextList(data.error));
  const hasGatewayVerdict = Boolean(gatewayResult?.decision);
  const headlineLabel = hasGatewayVerdict ? 'Gateway Verdict' : 'Agent / Session Status';

  return (
    <div className="gateway-result-panel">
      <div className="result-headline">
        <div>
          <span className="eyebrow">{headlineLabel}</span>
          <h2>{String(finalDecision).toUpperCase()}</h2>
        </div>
        <div className="result-badges">
          <Badge tone={getDecisionTone(finalDecision)}>{hasGatewayVerdict ? 'decision' : 'status'}: {String(finalDecision)}</Badge>
          {result.fromMock && <Badge tone="purple">Mock fallback</Badge>}
          {data.executed === true && <Badge tone="green">executed</Badge>}
          {data.executed === false && <Badge tone="blue">not executed</Badge>}
          {data.mode === 'plan_only' && <Badge tone="blue">plan only</Badge>}
        </div>
      </div>

      <div className="verdict-grid">
        <div>
          <span>调用接口</span>
          <strong>{result.endpoint || 'unknown'}</strong>
        </div>
        <div>
          <span>风险分数</span>
          <strong>{gatewayResult?.risk_score != null ? String(gatewayResult.risk_score) : '-'}</strong>
        </div>
        <div>
          <span>Pending ID</span>
          <strong>{data.pending_id ? String(data.pending_id) : '-'}</strong>
        </div>
      </div>

      {typeof data.message === 'string' && <p className="result-message">{data.message}</p>}
      {result.error && <p className="result-error">后端请求提示：{result.error}</p>}

      {agentResult && (
        <div className="pipeline-card">
          <div className="pipeline-title">
            <Badge tone="blue">1</Badge>
            <strong>Agent 规划结果</strong>
          </div>
          <div className="kv-grid">
            <span>Agent</span><code>{String(agentResult.agent || session?.agent_type || '-')}</code>
            <span>Status</span><code>{String(agentResult.status || session?.status || '-')}</code>
            <span>Confidence</span><code>{agentResult.confidence != null ? String(agentResult.confidence) : '-'}</code>
          </div>
          {Boolean(agentResult.clarification_question) && <p className="result-message">需要补充：{String(agentResult.clarification_question)}</p>}
        </div>
      )}

      {toolCall && (
        <div className="pipeline-card">
          <div className="pipeline-title">
            <Badge tone="purple">2</Badge>
            <strong>结构化工具调用</strong>
          </div>
          <div className="kv-grid">
            <span>Tool</span><code>{String(toolCall.tool_name || toolCall.tool || '-')}</code>
            <span>Description</span><code>{String(toolCall.description || '-')}</code>
          </div>
          <pre className="json-block">{stringify(toolCall.arguments || toolCall.params || {})}</pre>
        </div>
      )}

      {gatewayResult && (
        <div className="pipeline-card">
          <div className="pipeline-title">
            <Badge tone={getDecisionTone(gatewayResult.decision)}>3</Badge>
            <strong>Gateway / Runtime Monitor 判定</strong>
          </div>
          <div className="reason-list">
            {reasons.length ? reasons.map((reason, index) => <p key={index}>{reason}</p>) : <p>后端未返回具体 reason。</p>}
          </div>
        </div>
      )}

      {steps.length > 0 && (
        <div className="pipeline-card">
          <div className="pipeline-title">
            <Badge tone="yellow">LLM</Badge>
            <strong>多步运行链路</strong>
          </div>
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
          <h1>命令输入与授权判定工作台</h1>
          <p>
            这里不是单纯看指标，而是把用户自然语言任务送进 Agent，再由 FakeAgent / LLM 生成工具调用计划，最后交给 Gateway 或 Runtime Monitor 判断是否允许执行。
          </p>
        </div>
        <div className="flow-strip">
          <span>用户命令</span>
          <b>→</b>
          <span>Agent 规划</span>
          <b>→</b>
          <span>网关判定</span>
          <b>→</b>
          <span>执行 / 拦截 / 确认</span>
        </div>
      </section>

      <div className="workbench-layout">
        <Section
          eyebrow="Command Input"
          title="输入用户命令"
          description="建议课堂/比赛演示时默认使用 FakeAgent 规划 + Gateway 只判定，安全且能完整展示网关价值。"
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
                  <input
                    type="number"
                    min={1}
                    max={10}
                    value={input.maxSteps}
                    onChange={(event) => setInput({ ...input, maxSteps: Number(event.target.value) || 1 })}
                  />
                </label>
                <label>
                  <span>风险预算</span>
                  <input
                    type="number"
                    min={1}
                    max={200}
                    value={input.riskBudget}
                    onChange={(event) => setInput({ ...input, riskBudget: Number(event.target.value) || 80 })}
                  />
                </label>
              </div>
            )}

            <label>
              <span>自然语言命令</span>
              <textarea
                value={input.userInput}
                onChange={(event) => setInput({ ...input, userInput: event.target.value })}
                placeholder="例如：读取文件 public/notice.txt"
              />
            </label>

            <div className="command-actions">
              <button className="primary-btn" disabled={running || !input.userInput.trim()} onClick={() => void handleSubmit()}>
                {running ? '正在判定……' : '提交给网关判定'}
              </button>
              <button className="secondary-btn" onClick={() => setResult(null)}>清空结果</button>
            </div>
          </div>
        </Section>

        <Section
          eyebrow="Demo Cases"
          title="一键演示样例"
          description="这些样例对应公开读取、敏感读取、删除确认、邮件发送、Shell 命令和提示注入链路。"
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
        title="Agent 规划与网关判定结果"
        description="结果会同时展示 Agent 输出、结构化工具调用、Gateway 判定原因、多步 LLM 运行链路和原始 JSON。"
      >
        <ResultPanel result={result} />
      </Section>
    </div>
  );
}
