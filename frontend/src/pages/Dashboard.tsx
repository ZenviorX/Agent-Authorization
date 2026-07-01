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
          <span className="eyebrow">Local Runtime Evidence</span>
          <h1>AI Agent 工具调用授权网关</h1>
          <p>
            本页用于查看本机真实运行数据：Agent 工具调用进入 Tool Proxy、Gateway、Capability Token、Runtime Monitor、Sandbox Policy 与 Hybrid Sandbox 后，会形成 allow / confirm / deny 和审计证据。
          </p>
          <div className="hero-actions">
            <button className="secondary-btn small" type="button">数据：本地运行记录</button>
            <button className="secondary-btn small" type="button">执行：Hybrid Sandbox</button>
            <button className="secondary-btn small" type="button">证据：Audit / Evidence</button>
          </div>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <div className="orb orb-a" />
          <div className="orb orb-b" />
          <div className="gateway-card floating-card">
            <span>Gateway Decision</span>
            <strong>{highRisk.length > 0 ? 'Risk Controlled' : 'Normal'}</strong>
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
        <MetricCard title="本地请求记录" value={compactNumber(overview?.totalRequests ?? 0)} hint="由本地审计与沙箱运行记录聚合" icon="dashboard" />
        <MetricCard title="阻断请求" value={compactNumber(overview?.blockedRequests ?? 0)} hint="本地记录中 deny 的数量" icon="shield" />
        <MetricCard title="平均耗时" value={overview?.averageLatencyMs ?? 0} suffix="ms" hint="来自最新测试摘要" icon="spark" />
        <MetricCard title="安全评分" value={overview?.securityScore ?? 0} suffix="/100" hint="按本地测试结果估算" icon="check" />
      </div>

      <Section
        eyebrow="Requests"
        title="最近本地授权 / 沙箱记录"
        description="这里展示本机真实记录。运行授权演示后，再刷新本页即可看到新记录。"
        actions={<Badge tone="yellow">{pending.length} 个待确认</Badge>}
      >
        <RequestTable rows={requests.slice(0, 5)} onApprove={onApprove} onReject={onReject} compact />
      </Section>

      <section className="two-column">
        <Section eyebrow="Audit" title="本地审计时间线" description="用于说明系统为什么可追责：每次授权、拦截和沙箱执行都会留下本地证据。">
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

        <Section eyebrow="Architecture" title="提交展示主线" description="按这个顺序讲，老师能更快理解项目不是普通聊天页面。">
          <div className="architecture-card">
            <div>Agent</div>
            <span>→</span>
            <div>Tool Proxy</div>
            <span>→</span>
            <div>Gateway / Token</div>
            <span>→</span>
            <div>Sandbox / Evidence</div>
          </div>
          <div className="explain-box">
            <strong>核心卖点：</strong>
            <p>系统把 AI Agent 的工具调用从“直接执行”改造成“先授权、再校验、后沙箱执行、全程留证”的安全流程。</p>
          </div>
        </Section>
      </section>
    </div>
  );
}
