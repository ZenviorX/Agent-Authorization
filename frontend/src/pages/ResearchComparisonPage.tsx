import { useState } from 'react';
import { Badge } from '../components/Badge';
import { Section } from '../components/Section';

type ResearchCase = {
  id: string;
  scenario: string;
  is_risky: boolean;
  noguard: string;
  oauth_only: string;
  agentguard: string;
  research_value: string;
  summary: string;
};

type ResearchReport = {
  name: string;
  total_cases: number;
  risky_cases: number;
  metrics: {
    noguard_unsafe_allow_rate: number;
    oauth_only_unsafe_allow_rate: number;
    agentguard_unsafe_allow_rate: number;
  };
  cases: ResearchCase[];
};

function percent(value: number) {
  return `${(value * 100).toFixed(0)}%`;
}

export function ResearchComparisonPage() {
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [loading, setLoading] = useState(false);

  async function runComparison() {
    setLoading(true);
    try {
      const res = await fetch('/research/strategy-comparison/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });
      const data = await res.json();
      setReport(data as ResearchReport);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page-grid">
      <section className="workbench-hero">
        <div>
          <span className="eyebrow">Research Evaluation</span>
          <h1>NoGuard vs OAuth-only vs AgentGuard</h1>
          <p>
            这里用于展示科研级横向对比：无防护、只检查 OAuth scope、完整 AgentGuard 三种策略在风险样例上的误放行率。
          </p>
        </div>
        <button className="primary-btn" onClick={runComparison} disabled={loading}>
          {loading ? '运行中...' : '运行对比实验'}
        </button>
      </section>

      {report && (
        <>
          <div className="verdict-grid">
            <div>
              <span>NoGuard 误放行率</span>
              <strong>{percent(report.metrics.noguard_unsafe_allow_rate)}</strong>
            </div>
            <div>
              <span>OAuth-only 误放行率</span>
              <strong>{percent(report.metrics.oauth_only_unsafe_allow_rate)}</strong>
            </div>
            <div>
              <span>AgentGuard 误放行率</span>
              <strong>{percent(report.metrics.agentguard_unsafe_allow_rate)}</strong>
            </div>
          </div>

          <Section
            eyebrow="Research Cases"
            title="横向对比样例"
            description={`总样例 ${report.total_cases} 条，其中风险样例 ${report.risky_cases} 条。`}
          >
            <div className="pipeline-card">
              <table>
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Scenario</th>
                    <th>NoGuard</th>
                    <th>OAuth-only</th>
                    <th>AgentGuard</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  {report.cases.map((item) => (
                    <tr key={item.id}>
                      <td>{item.id}</td>
                      <td>{item.scenario}</td>
                      <td><Badge tone={item.noguard === 'allow' ? 'red' : 'green'}>{item.noguard}</Badge></td>
                      <td><Badge tone={item.oauth_only === 'allow' && item.is_risky ? 'red' : 'green'}>{item.oauth_only}</Badge></td>
                      <td><Badge tone={item.agentguard === 'deny' ? 'green' : 'yellow'}>{item.agentguard}</Badge></td>
                      <td>{item.research_value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>
        </>
      )}
    </div>
  );
}
