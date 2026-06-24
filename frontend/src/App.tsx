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
import type {
  AuditLog,
  EvaluationMetric,
  GatewayRequest,
  Overview,
  PolicyRule,
  StrategyComparisonResponse,
  SystemSetting
} from './types/domain';
import './styles/global.css';
import './styles/layout.css';

const navItems = [
  { key: 'workbench', label: '?????', icon: 'shield' },
  { key: 'dashboard', label: '????', icon: 'dashboard' },
  { key: 'requests', label: '????', icon: 'requests' },
  { key: 'policies', label: '????', icon: 'policies' },
  { key: 'audit', label: '????', icon: 'audit' },
  { key: 'evaluation', label: '????', icon: 'lab' },
  { key: 'settings', label: '????', icon: 'settings' }
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
  const [strategyComparison, setStrategyComparison] = useState<StrategyComparisonResponse | null>(null);
  const [settings, setSettings] = useState<SystemSetting[]>([]);

  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      const [
        overviewData,
        requestData,
        policyData,
        auditData,
        evaluationData,
        strategyComparisonData,
        settingData
      ] = await Promise.all([
        api.getOverview(),
        api.getRequests(),
        api.getPolicies(),
        api.getAuditLogs(),
        api.getEvaluations(),
        api.getStrategyComparison(),
        api.getSettings()
      ]);
      if (!mounted) return;
      setOverview(overviewData);
      setRequests(requestData);
      setPolicies(policyData);
      setAuditLogs(auditData);
      setEvaluations(evaluationData);
      setStrategyComparison(strategyComparisonData);
      setSettings(settingData);
      setLoading(false);
    }
    void load();
    return () => { mounted = false; };
  }, []);

  const currentTitle = useMemo(() => navItems.find((item) => item.key === page)?.label ?? '??', [page]);

  async function handleDecision(id: string, result: 'approved' | 'rejected') {
    await api.submitDecision(id, result);
    setRequests((old) => old.map((item) => item.id === id ? {
      ...item,
      status: result,
      decision: result === 'approved' ? 'allow' : 'deny',
      reason: result === 'approved' ? `${item.reason} ????????` : `${item.reason} ????????`
    } : item));
  }

  const content = {
    workbench: <GatewayWorkbench />,
    dashboard: <Dashboard overview={overview} requests={requests} auditLogs={auditLogs} onApprove={(id) => void handleDecision(id, 'approved')} onReject={(id) => void handleDecision(id, 'rejected')} />,
    requests: <RequestsPage requests={requests} onApprove={(id) => void handleDecision(id, 'approved')} onReject={(id) => void handleDecision(id, 'rejected')} />,
    policies: <PoliciesPage policies={policies} />,
    audit: <AuditPage logs={auditLogs} />,
    evaluation: <EvaluationPage metrics={evaluations} strategyComparison={strategyComparison} />,
    settings: <SettingsPage settings={settings} />
  }[page];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Icon name="shield" /></div>
          <div>
            <strong>ZenviorX</strong>
            <span>AI ????</span>
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
          <small>Command ? Agent ? Gateway ? {overview?.activePolicies ?? 0} policies</small>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <span className="eyebrow">????</span>
            <h1>{currentTitle}</h1>
          </div>
          <div className="topbar-actions">
            <div className="search-box">? ???? / ?? / ??</div>
            <button className="primary-btn small" onClick={() => setPage('workbench')}>????</button>
          </div>
        </header>

        {loading ? (
          <div className="loading-screen">
            <div className="loader" />
            <p>??????????</p>
          </div>
        ) : content}
      </main>
    </div>
  );
}
