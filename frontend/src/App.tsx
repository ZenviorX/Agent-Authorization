import { useEffect, useMemo, useState } from 'react';
import { Icon } from './components/Icon';
import { GatewayWorkbench } from './pages/GatewayWorkbench';
import { Dashboard } from './pages/Dashboard';
import { RequestsPage } from './pages/RequestsPage';
import { PoliciesPage } from './pages/PoliciesPage';
import { AuditPage } from './pages/AuditPage';
import { EvaluationPage } from './pages/EvaluationPage';
import { SettingsPage } from './pages/SettingsPage';
import { api } from './services/api';
import type { AuditLog, EvaluationMetric, GatewayRequest, Overview, PolicyRule, SystemSetting } from './types/domain';
import './styles/global.css';
import './styles/layout.css';

const navItems = [
  { key: 'workbench', label: '网关工作台', icon: 'shield' },
  { key: 'dashboard', label: '态势总览', icon: 'dashboard' },
  { key: 'requests', label: '请求审查', icon: 'requests' },
  { key: 'policies', label: '策略中心', icon: 'policies' },
  { key: 'audit', label: '审计日志', icon: 'audit' },
  { key: 'evaluation', label: '效果评测', icon: 'lab' },
  { key: 'settings', label: '系统设置', icon: 'settings' }
] as const;

type PageKey = typeof navItems[number]['key'];

export default function App() {
  const [page, setPage] = useState<PageKey>('workbench');
  const [loading, setLoading] = useState(true);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [requests, setRequests] = useState<GatewayRequest[]>([]);
  const [policies, setPolicies] = useState<PolicyRule[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [evaluations, setEvaluations] = useState<EvaluationMetric[]>([]);
  const [settings, setSettings] = useState<SystemSetting[]>([]);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      const [overviewData, requestData, policyData, auditData, evaluationData, settingData] = await Promise.all([
        api.getOverview(),
        api.getRequests(),
        api.getPolicies(),
        api.getAuditLogs(),
        api.getEvaluations(),
        api.getSettings()
      ]);
      if (!mounted) return;
      setOverview(overviewData);
      setRequests(requestData);
      setPolicies(policyData);
      setAuditLogs(auditData);
      setEvaluations(evaluationData);
      setSettings(settingData);
      setLoading(false);
    }
    void load();
    return () => { mounted = false; };
  }, []);

  const currentTitle = useMemo(() => navItems.find((item) => item.key === page)?.label ?? '总览', [page]);

  async function handleDecision(id: string, result: 'approved' | 'rejected') {
    await api.submitDecision(id, result);
    setRequests((old) => old.map((item) => item.id === id ? {
      ...item,
      status: result,
      decision: result === 'approved' ? 'allow' : 'deny',
      reason: result === 'approved' ? `${item.reason} 人工复核后通过。` : `${item.reason} 人工复核后拒绝。`
    } : item));
  }

  const content = {
    workbench: <GatewayWorkbench />,
    dashboard: <Dashboard overview={overview} requests={requests} auditLogs={auditLogs} onApprove={(id) => void handleDecision(id, 'approved')} onReject={(id) => void handleDecision(id, 'rejected')} />,
    requests: <RequestsPage requests={requests} onApprove={(id) => void handleDecision(id, 'approved')} onReject={(id) => void handleDecision(id, 'rejected')} />,
    policies: <PoliciesPage policies={policies} />,
    audit: <AuditPage logs={auditLogs} />,
    evaluation: <EvaluationPage metrics={evaluations} />,
    settings: <SettingsPage settings={settings} />
  }[page];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Icon name="shield" /></div>
          <div>
            <strong>ZenviorX</strong>
            <span>AI 安全网关</span>
          </div>
        </div>

        <nav className="nav-list">
          {navItems.map((item) => (
            <button
              key={item.key}
              className={page === item.key ? 'active' : ''}
              onClick={() => setPage(item.key)}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-card">
          <span>System Status</span>
          <strong>{loading ? 'Loading...' : 'Protected'}</strong>
          <small>Command → Agent → Gateway · {overview?.activePolicies ?? 0} policies</small>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <span className="eyebrow">当前页面</span>
            <h1>{currentTitle}</h1>
          </div>
          <div className="topbar-actions">
            <div className="search-box">⌕ 搜索请求 / 策略 / 日志</div>
            <button className="primary-btn small" onClick={() => setPage('workbench')}>输入命令</button>
          </div>
        </header>

        {loading ? (
          <div className="loading-screen">
            <div className="loader" />
            <p>正在加载网关数据……</p>
          </div>
        ) : content}
      </main>
    </div>
  );
}
