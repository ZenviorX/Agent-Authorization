import type { AuditLog, GatewayRequest, Overview } from '../types/domain';
import { compactNumber, decisionText } from '../utils/format';
import { Badge } from '../components/Badge';
import { MetricCard } from '../components/MetricCard';
import { RequestTable } from '../components/RequestTable';
import { Section } from '../components/Section';

interface DashboardProps {
  overview: Overview | null;
  requests: GatewayRequest[];
  auditLogs: AuditLog[];
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}

export function Dashboard({ overview, requests, auditLogs, onApprove, onReject }: DashboardProps) {
  const pending = requests.filter((item) => item.status === 'pending');
  const highRisk = requests.filter((item) => item.risk === 'high' || item.risk === 'critical');

  return (
    <div className="page-grid">
      <section className="hero-panel">
        <div className="hero-copy">
          <span className="eyebrow">AI Agent Security Gateway</span>
          <h1>把智能体工具调用，管成可审计、可解释、可阻断的安全流程。</h1>
          <p>
            面向信安赛/课程展示场景：请求准入、策略命中、人工确认、审计日志与评测指标集中展示。
          </p>
          <div className="hero-actions">
            <a className="primary-btn" href="#requests">查看待确认请求</a>
            <a className="secondary-btn" href="#policies">检查策略覆盖</a>
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="orb orb-a" />
          <div className="orb orb-b" />
          <div className="gateway-card floating-card">
            <span>Gateway Decision</span>
            <strong>{highRisk.length > 0 ? 'High Risk Blocked' : 'Normal'}</strong>
            <small>Policy hit rate {overview?.policyHitRate ?? 0}%</small>
          </div>
          <div className="gateway-card floating-card secondary">
            <span>Human Confirm</span>
            <strong>{pending.length} pending</strong>
            <small>Side-effect operations</small>
          </div>
        </div>
      </section>

      <div className="metric-grid">
        <MetricCard title="总请求量" value={compactNumber(overview?.totalRequests ?? 0)} hint="今日网关处理请求" icon="dashboard" />
        <MetricCard title="阻断请求" value={compactNumber(overview?.blockedRequests ?? 0)} hint="越权、危险命令、敏感资源" icon="shield" />
        <MetricCard title="平均耗时" value={overview?.averageLatencyMs ?? 0} suffix="ms" hint="策略判定平均延迟" icon="spark" />
        <MetricCard title="安全评分" value={overview?.securityScore ?? 0} suffix="/100" hint="按命中率与误拦率综合估算" icon="check" />
      </div>

      <Section
        eyebrow="Requests"
        title="最近网关请求"
        description="展示智能体、用户、工具目标、策略解释与最终决策。"
        actions={<Badge tone="yellow">{pending.length} 个待确认</Badge>}
      >
        <RequestTable rows={requests.slice(0, 5)} onApprove={onApprove} onReject={onReject} compact />
      </Section>

      <section className="two-column">
        <Section eyebrow="Audit" title="审计时间线" description="适合答辩时说明系统为什么可信、可追责。">
          <div className="timeline">
            {auditLogs.map((log) => (
              <article className="timeline-item" key={log.id}>
                <span className="timeline-dot" />
                <div>
                  <div className="timeline-title">
                    <strong>{log.action}</strong>
                    <Badge>{decisionText[log.result]}</Badge>
                  </div>
                  <p>{log.detail}</p>
                  <small>{log.timestamp} · {log.actor} · {log.resource}</small>
                </div>
              </article>
            ))}
          </div>
        </Section>

        <Section eyebrow="Architecture" title="推荐展示结构" description="可以直接照着这张逻辑讲项目。">
          <div className="architecture-card">
            <div>Agent 请求</div>
            <span>→</span>
            <div>安全网关</div>
            <span>→</span>
            <div>策略引擎</div>
            <span>→</span>
            <div>工具执行器</div>
          </div>
          <div className="explain-box">
            <strong>核心卖点：</strong>
            <p>不是简单做一个聊天界面，而是在智能体调用工具之前加入统一准入层，输出 allow / deny / confirm / review，并保留审计证据。</p>
          </div>
        </Section>
      </section>
    </div>
  );
}
