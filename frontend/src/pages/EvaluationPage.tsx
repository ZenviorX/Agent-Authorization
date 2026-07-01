import type { EvaluationMetric, StrategyComparisonResponse, TestResultSummary } from '../types/domain';
import { MetricCard } from '../components/MetricCard';
import { Section } from '../components/Section';

function formatRate(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0.00%';
  return `${(value * 100).toFixed(2)}%`;
}

function formatPercentNumber(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0.00';
  return (value * 100).toFixed(2);
}

function formatMs(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0.00 ms';
  return `${value.toFixed(2)} ms`;
}

function renderDistribution(title: string, data?: Record<string, number>) {
  const entries = Object.entries(data ?? {});

  if (entries.length === 0) {
    return <div><strong>{title}</strong><span>暂无数据</span></div>;
  }

  return (
    <div>
      <strong>{title}</strong>
      {entries.slice(0, 6).map(([key, value]) => (
        <span key={key}>{key}: {value}</span>
      ))}
    </div>
  );
}

const strategyNames: Record<string, string> = {
  allow_all: 'Allow All',
  keyword_only: 'Keyword Only',
  gateway: 'AgentGuard Gateway'
};

const strategyDescriptions: Record<string, string> = {
  allow_all: '无授权边界，全部放行，仅作为风险对照',
  keyword_only: '只按关键词拦截，容易漏掉上下文和任务边界风险',
  gateway: '使用 AgentGuard 授权网关，结合策略、任务边界、运行时监控和沙箱证据'
};

export function EvaluationPage({
  metrics,
  strategyComparison,
  testSummary,
  testRunning,
  testRunMessage,
  onRunTests,
  onRefreshTestSummary
}: {
  metrics: EvaluationMetric[];
  strategyComparison: StrategyComparisonResponse | null;
  testSummary: TestResultSummary | null;
  testRunning: boolean;
  testRunMessage: string | null;
  onRunTests: () => void;
  onRefreshTestSummary: () => void;
}) {
  const summary = strategyComparison?.summary ?? {};
  const strategies = ['allow_all', 'keyword_only', 'gateway'].filter((name) => summary[name]);
  const latestTestAvailable = Boolean(testSummary?.available);

  return (
    <div className="page-grid">
      <section className="workbench-hero">
        <div>
          <span className="eyebrow">Test Report</span>
          <h1>Gateway 独立测试报告</h1>
          <p>
            本页只负责提交前验证：运行 `test.run`，读取 `test/cases/gateway_cases*.json`，将样例输入 Gateway，并把通过率、风险阻断率、误放行率等指标同步到前端。
          </p>
        </div>
        <div className="flow-strip">
          <span>test/cases</span>
          <b>→</b>
          <span>Gateway</span>
          <b>→</b>
          <span>latest_summary.json</span>
          <b>→</b>
          <span>前端报告</span>
        </div>
      </section>

      <Section
        eyebrow="Independent Test Module"
        title="自动测试结果"
        description="这是当前最可信的评测入口；旧策略横向对比只作为辅助说明。"
        actions={(
          <div className="row-actions">
            <button className="secondary-btn small" onClick={onRefreshTestSummary} disabled={testRunning}>刷新结果</button>
            <button className="primary-btn small" onClick={onRunTests} disabled={testRunning}>
              {testRunning ? '测试运行中...' : '一键运行测试'}
            </button>
          </div>
        )}
      >
        <div className="metric-grid compact">
          <MetricCard title="测试样例" value={testSummary?.total_cases ?? 0} suffix=" cases" hint="本轮输入 Gateway 的样例数量" icon="lab" />
          <MetricCard title="通过样例" value={testSummary?.passed_cases ?? 0} suffix=" cases" hint="实际 decision 与预期匹配的样例" icon="check" />
          <MetricCard title="失败样例" value={testSummary?.failed_cases ?? 0} suffix=" cases" hint="实际 decision 与预期不一致的样例" icon="shield" />
          <MetricCard title="准确率" value={formatPercentNumber(testSummary?.accuracy)} suffix="%" hint="passed_cases / total_cases" icon="spark" />
        </div>

        <div className="metric-grid compact">
          <MetricCard title="风险阻断/确认率" value={formatPercentNumber(testSummary?.risk_block_or_confirm_rate)} suffix="%" hint="风险样例被 confirm 或 deny 的比例" icon="shield" />
          <MetricCard title="风险误放行率" value={formatPercentNumber(testSummary?.risk_unsafe_allow_rate)} suffix="%" hint="风险样例被错误 allow 的比例" icon="arrow" />
          <MetricCard title="正常误拒率" value={formatPercentNumber(testSummary?.normal_false_deny_rate)} suffix="%" hint="正常样例被 deny 的比例" icon="dashboard" />
          <MetricCard title="平均延迟" value={testSummary?.avg_latency_ms ?? 0} suffix=" ms" hint="Gateway 判定平均耗时" icon="spark" />
        </div>

        <div className="matrix-grid">
          {renderDistribution('决策分布', testSummary?.decision_distribution)}
          {renderDistribution('类别分布', testSummary?.category_distribution)}
          {renderDistribution('工具分布', testSummary?.tool_distribution)}
        </div>

        <div className="code-panel">
          <strong>{latestTestAvailable ? '最新测试结果已生成' : '暂无最新测试结果'}</strong>
          <code>{testSummary?.generated_at ?? testSummary?.hint ?? '点击“一键运行测试”生成结果'}</code>
          <small>{testRunMessage ?? testSummary?.message ?? '按钮会调用后端 /test-results/run，并刷新 test/results/latest_summary.json。'}</small>
        </div>
      </Section>

      <Section
        eyebrow="Result Files"
        title="测试产物位置"
        description={`独立测试运行后会生成 JSON、CSV、Markdown 和 HTML 看板；运行产物默认被 git ignore。耗时 ${formatMs(testSummary?.elapsed_ms)}。`}
      >
        <div className="matrix-grid">
          <div><strong>摘要 JSON</strong><span>{testSummary?.outputs?.latest_summary ?? 'test/results/latest_summary.json'}</span></div>
          <div><strong>样例明细</strong><span>{testSummary?.outputs?.latest_cases ?? 'test/results/latest_cases.json'}</span></div>
          <div><strong>CSV 明细</strong><span>{testSummary?.outputs?.latest_detail_csv ?? 'test/results/latest_detail.csv'}</span></div>
          <div><strong>Markdown 报告</strong><span>{testSummary?.outputs?.latest_report_md ?? 'test/results/latest_report.md'}</span></div>
          <div><strong>HTML 看板</strong><span>{testSummary?.outputs?.latest_dashboard_html ?? 'test/results/latest_dashboard.html'}</span></div>
          <div><strong>运行目录</strong><span>{testSummary?.outputs?.run_summary ?? 'test/results/run_YYYYMMDD_HHMMSS/'}</span></div>
        </div>
      </Section>

      <Section
        eyebrow="Auxiliary Metrics"
        title="前端辅助指标"
        description="这些是界面展示用辅助指标；提交时以独立测试模块结果为准。"
      >
        <div className="metric-grid compact">
          {metrics.map((metric) => (
            <MetricCard
              key={metric.name}
              title={metric.name}
              value={metric.value}
              suffix={metric.unit}
              hint={metric.description}
              icon={metric.trend === 'down' ? 'arrow' : 'spark'}
            />
          ))}
        </div>
      </Section>

      <Section
        eyebrow="Baseline Comparison"
        title="历史策略对照"
        description="保留 allow_all、keyword_only 与 gateway 对比，用于说明为什么需要 AgentGuard；不作为当前主评测入口。"
      >
        {strategyComparison?.available ? (
          <>
            <div className="metric-grid compact">
              <MetricCard title="测试样例" value={strategyComparison.total_cases} suffix=" cases" hint="参与横向对照的用例数量" icon="lab" />
              <MetricCard title="评测记录" value={strategyComparison.total_records} suffix=" rows" hint="策略与样例组合后的总记录数" icon="dashboard" />
              <MetricCard title="耗时" value={Number(strategyComparison.elapsed_ms.toFixed(2))} suffix=" ms" hint="本轮对照执行时间" icon="spark" />
            </div>

            <div className="matrix-grid">
              {strategies.map((name) => {
                const item = summary[name];
                return (
                  <div key={name}>
                    <strong>{strategyNames[name] ?? name}</strong>
                    <span>{strategyDescriptions[name] ?? '暂无策略说明'}</span>
                    <span>攻击拦截率：{formatRate(item.attack_block_or_confirm_rate)}</span>
                    <span>攻击误放行率：{formatRate(item.attack_allow_rate)}</span>
                    <span>正常样例通过率：{formatRate(item.normal_not_denied_rate)}</span>
                    <span>决策匹配率：{formatRate(item.decision_match_rate)}</span>
                  </div>
                );
              })}
            </div>
          </>
        ) : (
          <div className="empty-state">
            <strong>历史策略对照结果未接入</strong>
            <p>{strategyComparison?.hint ?? '当前推荐使用上方独立测试模块。'}</p>
          </div>
        )}
      </Section>
    </div>
  );
}
