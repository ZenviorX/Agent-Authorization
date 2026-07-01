import { useEffect, useMemo, useState } from 'react';
import { Icon } from './components/Icon';
import { GatewayWorkbench } from './pages/GatewayWorkbench';
import { Dashboard } from './pages/Dashboard';
import { RequestsPage } from './pages/RequestsPage';
import { PoliciesPage } from './pages/PoliciesPage';
import { AuditPage } from './pages/AuditPage';
import { EvaluationPage } from './pages/EvaluationPage';
import { ResearchComparisonPage } from './pages/ResearchComparisonPage';
import { TwoPhaseAuthorizationPage } from './pages/TwoPhaseAuthorizationPage';
import { SettingsPage } from './pages/SettingsPage';
import { api } from './services/api';
import type {
  AuditLog,
  EvaluationMetric,
  GatewayRequest,
  Overview,
  PolicyRule,
  StrategyComparisonResponse,
  SystemSetting,
  TestResultSummary
} from './types/domain';
import './styles/global.css';
import './styles/layout.css';

const navSections = [
  {
    title: '一、核心演示',
    items: [
      {
        key: 'workbench',
        label: '授权工作台',
        icon: 'shield',
        description: '输入任务，展示 Agent → Gateway → Token → Sandbox → Evidence 主链路。'
      },
      {
        key: 'twoPhase',
        label: '两阶段授权',
        icon: 'shield',
        description: '解释 Capability Token 的签发、绑定和执行阶段消费。'
      }
    ]
  },
  {
    title: '二、运行数据',
    items: [
      {
        key: 'dashboard',
        label: '总览仪表盘',
        icon: 'dashboard',
        description: '概览网关请求、风险状态、审计时间线和推荐汇报主线。'
      },
      {
        key: 'requests',
        label: '授权请求',
        icon: 'requests',
        description: '查看 allow / confirm / deny 请求和人工确认入口。'
      },
      {
        key: 'audit',
        label: '审计日志',
        icon: 'audit',
        description: '查看授权判定和工具调用的审计记录。'
      }
    ]
  },
  {
    title: '三、规则与评测',
    items: [
      {
        key: 'policies',
        label: '策略管理',
        icon: 'policies',
        description: '展示策略规则、命中逻辑和风险控制边界。'
      },
      {
        key: 'evaluation',
        label: '测试报告',
        icon: 'lab',
        description: '运行独立 test 模块，展示 Gateway 评测结果。'
      },
      {
        key: 'research',
        label: '项目说明',
        icon: 'lab',
        description: '说明 NoGuard、OAuth-only 与 AgentGuard 的差异。'
      }
    ]
  },
  {
    title: '四、系统配置',
    items: [
      {
        key: 'settings',
        label: '系统设置',
        icon: 'settings',
        description: '展示当前演示环境和基础配置项。'
      }
    ]
  }
] as const;

const navItems = navSections.flatMap((section) => section.items);
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
  const [testSummary, setTestSummary] = useState<TestResultSummary | null>(null);
  const [testRunning, setTestRunning] = useState(false);
  const [testRunMessage, setTestRunMessage] = useState<string | null>(null);
  const [settings, setSettings] = useState<SystemSetting[]>([]);

  async function refreshTestSummary() {
    const summary = await api.getTestResultSummary();
    setTestSummary(summary);
    return summary;
  }

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
        testSummaryData,
        settingData
      ] = await Promise.all([
        api.getOverview(),
        api.getRequests(),
        api.getPolicies(),
        api.getAuditLogs(),
        api.getEvaluations(),
        api.getStrategyComparison(),
        api.getTestResultSummary(),
        api.getSettings()
      ]);

      if (!mounted) return;
      setOverview(overviewData);
      setRequests(requestData);
      setPolicies(policyData);
      setAuditLogs(auditData);
      setEvaluations(evaluationData);
      setStrategyComparison(strategyComparisonData);
      setTestSummary(testSummaryData);
      setSettings(settingData);
      setLoading(false);
    }

    void load();
    return () => { mounted = false; };
  }, []);

  const currentNavItem = useMemo(() => navItems.find((item) => item.key === page), [page]);
  const currentTitle = currentNavItem?.label ?? '页面';
  const currentDescription = currentNavItem?.description ?? 'AgentGuard 项目提交版前端。';

  async function handleDecision(id: string, result: 'approved' | 'rejected') {
    await api.submitDecision(id, result);
    setRequests((old) => old.map((item) => item.id === id ? {
      ...item,
      status: result,
      decision: result === 'approved' ? 'allow' : 'deny',
      reason: result === 'approved' ? `${item.reason}（已人工批准）` : `${item.reason}（已人工拒绝）`
    } : item));
  }

  async function handleRunIndependentTests() {
    setTestRunning(true);
    setTestRunMessage('正在运行独立测试模块，请稍候...');

    try {
      const result = await api.runIndependentTests();
      setTestSummary(result.summary);
      setTestRunMessage(
        result.success
          ? `测试完成：${result.summary.passed_cases}/${result.summary.total_cases} 通过。`
          : `测试执行失败：退出码 ${result.returncode}。`
      );
    } catch (error) {
      setTestRunMessage(error instanceof Error ? error.message : '测试执行失败。');
      await refreshTestSummary();
    } finally {
      setTestRunning(false);
    }
  }

  const content = {
    workbench: <GatewayWorkbench />,
    dashboard: <Dashboard overview={overview} requests={requests} auditLogs={auditLogs} onApprove={(id) => void handleDecision(id, 'approved')} onReject={(id) => void handleDecision(id, 'rejected')} />,
    requests: <RequestsPage requests={requests} onApprove={(id) => void handleDecision(id, 'approved')} onReject={(id) => void handleDecision(id, 'rejected')} />,
    policies: <PoliciesPage policies={policies} />,
    audit: <AuditPage logs={auditLogs} />,
    evaluation: (
      <EvaluationPage
        metrics={evaluations}
        strategyComparison={strategyComparison}
        testSummary={testSummary}
        testRunning={testRunning}
        testRunMessage={testRunMessage}
        onRunTests={() => void handleRunIndependentTests()}
        onRefreshTestSummary={() => void refreshTestSummary()}
      />
    ),
    research: <ResearchComparisonPage />,
    twoPhase: <TwoPhaseAuthorizationPage />,
    settings: <SettingsPage settings={settings} />
  }[page];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><Icon name="shield" /></div>
          <div>
            <strong>AgentGuard</strong>
            <span>智能体工具调用授权网关</span>
          </div>
        </div>

        <nav className="nav-list" aria-label="AgentGuard frontend navigation">
          {navSections.map((section) => (
            <div className="nav-section" key={section.title}>
              <small>{section.title}</small>
              {section.items.map((item) => (
                <button
                  key={item.key}
                  className={page === item.key ? 'active' : ''}
                  onClick={() => setPage(item.key)}
                  title={item.description}
                >
                  <Icon name={item.icon} />
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-card">
          <span>Submission Status</span>
          <strong>{loading ? 'Loading...' : 'Ready'}</strong>
          <small>Agent → Gateway → Token → Sandbox → Evidence</small>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div>
            <span className="eyebrow">AgentGuard Final Demo</span>
            <h1>{currentTitle}</h1>
            <p className="topbar-desc">{currentDescription}</p>
          </div>
          <div className="topbar-actions">
            <span className="status-pill">提交版主线</span>
            <button className="primary-btn small" onClick={() => setPage('workbench')}>进入授权演示</button>
          </div>
        </header>

        {loading ? (
          <div className="loading-screen">
            <div className="loader" />
            <p>正在加载 AgentGuard 前端数据...</p>
          </div>
        ) : content}
      </main>
    </div>
  );
}
