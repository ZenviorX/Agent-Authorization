import { useState } from 'react';
import { Badge } from '../components/Badge';
import { Section } from '../components/Section';

type ToolProxyResponse = {
  decision: string;
  executed: boolean;
  capability_token?: {
    issued?: boolean;
    token?: string;
    reason?: string;
  };
  authorization_trace?: Array<{
    stage: string;
    decision: string;
    reason: string[];
    extra: Record<string, unknown>;
  }>;
};

const baseRequest = {
  user: 'user',
  original_task: '请读取 public/notice.txt 并总结',
  tool: 'file.read',
  params: {
    path: 'public/notice.txt'
  },
  requested_scopes: ['tool:file:read'],
  oauth_token_claims: {
    scope: 'tool:file:read'
  },
  auth_mode: 'oauth_scope',
  agent_platform: 'openclaw',
  sandbox_profile: 'local_readonly'
};

export function TwoPhaseAuthorizationPage() {
  const [phase1, setPhase1] = useState<ToolProxyResponse | null>(null);
  const [phase2, setPhase2] = useState<ToolProxyResponse | null>(null);
  const [replay, setReplay] = useState<ToolProxyResponse | null>(null);
  const [status, setStatus] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  async function postJson(url: string, body: unknown) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    return res.json();
  }

  async function runDemo() {
    setLoading(true);
    setPhase1(null);
    setPhase2(null);
    setReplay(null);
    setStatus(null);

    try {
      const prepareResult = await postJson('/tool-proxy/two-phase/prepare', {
        ...baseRequest,
        execute: false,
        capability_token: ''
      }) as ToolProxyResponse;

      setPhase1(prepareResult);

      const token = prepareResult.capability_token?.token;
      if (!token) return;

      const executeResult = await postJson('/tool-proxy/two-phase/execute', {
        ...baseRequest,
        execute: true,
        capability_token: token
      }) as ToolProxyResponse;

      setPhase2(executeResult);

      const statusResult = await postJson('/tool-proxy/capability-token/status', {
        token
      });

      setStatus(statusResult);

      const replayResult = await postJson('/tool-proxy/two-phase/execute', {
        ...baseRequest,
        execute: true,
        capability_token: token
      }) as ToolProxyResponse;

      setReplay(replayResult);
    } finally {
      setLoading(false);
    }
  }

  function renderTrace(result: ToolProxyResponse | null) {
    if (!result?.authorization_trace?.length) {
      return <p className="muted">暂无授权 Trace。</p>;
    }

    return (
      <div className="matrix-grid">
        {result.authorization_trace.map((item) => (
          <div key={item.stage}>
            <strong>{item.stage}</strong>
            <Badge tone={item.decision === 'allow' ? 'green' : item.decision === 'deny' ? 'red' : 'yellow'}>
              {item.decision}
            </Badge>
            <span>{item.reason?.join(' / ')}</span>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="page-grid">
      <section className="workbench-hero">
        <div>
          <span className="eyebrow">Two-phase Authorization</span>
          <h1>两阶段工具调用授权</h1>
          <p>
            prepare 阶段只授权并签发任务级 Capability Token；execute 阶段必须携带该 token 才能真正执行工具，执行后 token 被消费，不能重放。
          </p>
        </div>
        <button className="primary-btn" onClick={runDemo} disabled={loading}>
          {loading ? '运行中...' : '运行两阶段演示'}
        </button>
      </section>

      <div className="verdict-grid">
        <div>
          <span>Prepare</span>
          <strong>{phase1?.decision ?? '-'}</strong>
          <small>token issued: {String(phase1?.capability_token?.issued ?? false)}</small>
        </div>
        <div>
          <span>Execute</span>
          <strong>{phase2?.decision ?? '-'}</strong>
          <small>executed: {String(phase2?.executed ?? false)}</small>
        </div>
        <div>
          <span>Replay</span>
          <strong>{replay?.decision ?? '-'}</strong>
          <small>同一 token 二次执行应被拒绝</small>
        </div>
      </div>

      <Section
        eyebrow="Capability Token"
        title="Token 生命周期状态"
        description="展示 token 从 issued 到 consumed 的状态变化。"
      >
        <div className="code-panel">
          <strong>Ledger Status</strong>
          <pre>{JSON.stringify(status, null, 2)}</pre>
        </div>
      </Section>

      <Section
        eyebrow="Authorization Trace"
        title="Execute 阶段授权链路"
        description="展示 OAuth Scope、Capability Token、Task Boundary、Sandbox Policy 和最终决策。"
      >
        {renderTrace(phase2)}
      </Section>

      <Section
        eyebrow="Replay Protection"
        title="重放拦截 Trace"
        description="同一个 token 已经被消费后，再次执行应在 capability_token 阶段被拒绝。"
      >
        {renderTrace(replay)}
      </Section>
    </div>
  );
}
