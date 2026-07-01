import { useState } from 'react';
import { Badge } from '../components/Badge';
import { Section } from '../components/Section';
import { api } from '../services/api';
import type { AgentCommandInput, AgentCommandResponse, AgentRunMode } from '../types/domain';

type JsonRecord = Record<string, unknown>;
type BadgeTone = 'green' | 'red' | 'yellow' | 'blue' | 'purple' | 'gray';

const modes: Array<{
  value: AgentRunMode;
  label: string;
  short: string;
  description: string;
}> = [
  {
    value: 'fake_check',
    label: '普通授权判定',
    short: '只判断，不执行',
    description: '适合先演示：Agent 把自然语言转为工具调用，Gateway 输出 allow / confirm / deny。'
  },
  {
    value: 'docker_sandbox_execute',
    label: '真沙箱执行',
    short: '自动选择 Docker / Native',
    description: '适合重点展示：通过 Capability Token 后进入沙箱执行，并返回 evidence 证据。'
  },
  {
    value: 'tool_proxy_oauth',
    label: '外部 Agent 授权',
    short: 'OAuth-style scope 检查',
    description: '适合解释老师关心的 OAuth / WorkBuddy / OpenClaw 场景。'
  }
];

const samples: Array<{
  title: string;
  description: string;
  user: string;
  text: string;
  mode: AgentRunMode;
}> = [
  {
    title: '公开文件读取',
    description: '低风险读取，应当 allow。',
    user: 'user',
    text: '读取文件 public/notice.txt',
    mode: 'fake_check'
  },
  {
    title: '敏感文件拦截',
    description: '访问 secret，应当 deny。',
    user: 'user',
    text: '读取文件 secret/password.txt',
    mode: 'fake_check'
  },
  {
    title: '真沙箱读取',
    description: '进入 Native / Docker 沙箱并生成 evidence。',
    user: 'user',
    text: '真沙箱读取 public/notice.txt',
    mode: 'docker_sandbox_execute'
  },
  {
    title: '真沙箱写入',
    description: '只允许写入 outbox。',
    user: 'user',
    text: '真沙箱写入 outbox/docker_demo.txt',
    mode: 'docker_sandbox_execute'
  },
  {
    title: 'OAuth 外发拒绝',
    description: 'scope 不足却请求邮件外发，应当 deny。',
    user: 'user',
    text: 'WorkBuddy scope 不足但尝试发送外部邮箱',
    mode: 'tool_proxy_oauth'
  }
];

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function getRecord(source: JsonRecord | undefined, key: string): JsonRecord | undefined {
  const value = source?.[key];
  return isRecord(value) ? value : undefined;
}

function getDecisionTone(decision: unknown): BadgeTone {
  if (decision === 'allow' || decision === true) return 'green';
  if (decision === 'confirm') return 'yellow';
  if (decision === 'deny' || decision === false) return 'red';
  return 'blue';
}

function toText(value: unknown) {
  if (Array.isArray(value)) return value.map((item) => String(item)).join('；');
  if (value === undefined || value === null || value === '') return '-';
  return String(value);
}

function stringify(value: unknown) {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function extractResult(data: JsonRecord) {
  const proxyResult = getRecord(data, 'proxy_result');
  const executionResult = getRecord(data, 'execution_result');
  const gatewayResult = getRecord(data, 'gateway_result') || proxyResult || data;
  const agentResult = getRecord(data, 'agent_result');
  const agentToolCall = getRecord(agentResult, 'tool_call');
  const sandboxEvidence = getRecord(data, 'sandbox_evidence')
    || getRecord(executionResult, 'sandbox_evidence')
    || getRecord(proxyResult, 'sandbox_evidence');
  const sandboxPolicy = getRecord(sandboxEvidence, 'runtime_policy');

  const decision = gatewayResult?.decision || data.decision || 'unknown';
  const riskScore = gatewayResult?.risk_score || data.risk_score || '-';
  const reason = gatewayResult?.reason || data.reason || data.message || '-';
  const tool = agentToolCall?.tool_name || data.tool || gatewayResult?.tool || '-';
  const params = agentToolCall?.arguments || data.params || gatewayResult?.params || {};

  return {
    decision,
    riskScore,
    reason,
    tool,
    params,
    sandboxEvidence,
    sandboxPolicy
  };
}

function ResultPanel({ result }: { result: AgentCommandResponse | null }) {
  if (!result) {
    return (
      <div className="result-placeholder clean-placeholder">
        <strong>等待演示</strong>
        <p>选择一个样例，或输入任务后点击“运行演示”。结果会显示授权结论、风险分数、工具调用和沙箱证据。</p>
      </div>
    );
  }

  const data = result.data;
  const extracted = extractResult(data);
  const evidence = extracted.sandboxEvidence;
  const policy = extracted.sandboxPolicy;
  const paths = getRecord(evidence, 'paths');

  return (
    <div className="gateway-result-panel compact-result">
      <div className="result-headline">
        <div>
          <span className="eyebrow">授权结论</span>
          <h2>{String(extracted.decision).toUpperCase()}</h2>
        </div>
        <div className="result-badges">
          <Badge tone={getDecisionTone(extracted.decision)}>decision: {String(extracted.decision)}</Badge>
          {data.executed === true && <Badge tone="green">已执行</Badge>}
          {evidence && <Badge tone="blue">{String(evidence.sandbox_type || 'sandbox')}</Badge>}
        </div>
      </div>

      <div className="verdict-grid clean-verdict-grid">
        <div><span>调用链路</span><strong>{result.endpoint || '-'}</strong></div>
        <div><span>风险分数</span><strong>{String(extracted.riskScore)}</strong></div>
        <div><span>执行状态</span><strong>{data.executed === true ? '已进入沙箱' : '仅完成判定'}</strong></div>
      </div>

      <div className="pipeline-card">
        <div className="pipeline-title">
          <Badge tone={getDecisionTone(extracted.decision)}>Gateway</Badge>
          <strong>判定原因</strong>
        </div>
        <p className="plain-text">{toText(extracted.reason)}</p>
      </div>

      <div className="pipeline-card">
        <div className="pipeline-title">
          <Badge tone="purple">Tool</Badge>
          <strong>结构化工具调用</strong>
        </div>
        <div className="kv-grid">
          <span>Tool</span><code>{toText(extracted.tool)}</code>
          <span>Params</span><code>{stringify(extracted.params)}</code>
        </div>
      </div>

      {evidence && (
        <div className="pipeline-card">
          <div className="pipeline-title">
            <Badge tone="green">Sandbox</Badge>
            <strong>沙箱执行证据</strong>
          </div>
          <div className="kv-grid">
            <span>Type</span><code>{toText(evidence.sandbox_type)}</code>
            <span>Profile</span><code>{toText(evidence.sandbox_profile)}</code>
            <span>Network</span><code>{toText(policy?.network)}</code>
            <span>Evidence</span><code>{toText(paths?.evidence)}</code>
            <span>Hash</span><code>{toText(evidence.evidence_hash)}</code>
          </div>
          <p className="plain-text">无 Docker 环境下会使用 Native Subprocess Sandbox；有 Docker 时可切换为容器执行。</p>
        </div>
      )}

      <details className="raw-json">
        <summary>查看完整 JSON</summary>
        <pre className="json-block">{stringify(data)}</pre>
      </details>
    </div>
  );
}

export function GatewayWorkbench() {
  const [input, setInput] = useState<AgentCommandInput>({
    user: 'user',
    userInput: '真沙箱读取 public/notice.txt',
    mode: 'docker_sandbox_execute',
    maxSteps: 5,
    riskBudget: 80
  });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<AgentCommandResponse | null>(null);

  const selectedMode = modes.find((mode) => mode.value === input.mode) ?? modes[0];

  function applySample(sample: typeof samples[number]) {
    setInput({
      user: sample.user,
      userInput: sample.text,
      mode: sample.mode,
      maxSteps: 5,
      riskBudget: 80
    });
    setResult(null);
  }

  async function handleSubmit() {
    setRunning(true);
    try {
      const response = await api.runCommand(input);
      setResult(response);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="page-grid clean-page-grid">
      <section className="workbench-hero clean-hero">
        <div>
          <span className="eyebrow">Step 1</span>
          <h1>选择一个任务，查看授权结果</h1>
          <p>这是项目的主入口。建议先点“真沙箱读取”，再演示“敏感文件拦截”和“OAuth 外发拒绝”。</p>
        </div>
        <div className="flow-strip clean-flow">
          <span>Agent</span>
          <b>→</b>
          <span>Gateway</span>
          <b>→</b>
          <span>Token</span>
          <b>→</b>
          <span>Sandbox</span>
        </div>
      </section>

      <section className="clean-workbench-grid">
        <Section
          eyebrow="Input"
          title="演示输入"
          description="只保留三个核心模式，避免把调试入口暴露给老师。"
        >
          <div className="command-form compact-form">
            <label>
              <span>演示模式</span>
              <select value={input.mode} onChange={(event) => setInput({ ...input, mode: event.target.value as AgentRunMode })}>
                {modes.map((mode) => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
              </select>
            </label>

            <div className="mode-description clean-mode-description">
              <strong>{selectedMode.label}</strong>
              <p>{selectedMode.short}。{selectedMode.description}</p>
            </div>

            <label>
              <span>用户身份</span>
              <select value={input.user} onChange={(event) => setInput({ ...input, user: event.target.value })}>
                <option value="user">普通用户 user</option>
                <option value="admin">管理员 admin</option>
              </select>
            </label>

            <label>
              <span>自然语言任务</span>
              <textarea
                value={input.userInput}
                onChange={(event) => setInput({ ...input, userInput: event.target.value })}
                placeholder="例如：真沙箱读取 public/notice.txt"
              />
            </label>

            <div className="command-actions">
              <button className="primary-btn" disabled={running || !input.userInput.trim()} onClick={() => void handleSubmit()}>
                {running ? '运行中...' : '运行演示'}
              </button>
              <button className="secondary-btn" onClick={() => setResult(null)}>清空结果</button>
            </div>
          </div>
        </Section>

        <Section
          eyebrow="Samples"
          title="推荐样例"
          description="按顺序点击即可完成提交演示。"
        >
          <div className="sample-grid clean-sample-grid">
            {samples.map((sample, index) => (
              <button key={sample.title} className="sample-card clean-sample-card" onClick={() => applySample(sample)}>
                <span>{index + 1}</span>
                <strong>{sample.title}</strong>
                <small>{sample.description}</small>
                <code>{sample.text}</code>
              </button>
            ))}
          </div>
        </Section>
      </section>

      <Section
        eyebrow="Result"
        title="授权与执行结果"
        description="只展示最关键的信息：结论、原因、工具调用、沙箱证据。完整 JSON 放在折叠区。"
      >
        <ResultPanel result={result} />
      </Section>
    </div>
  );
}
