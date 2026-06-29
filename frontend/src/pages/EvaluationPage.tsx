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
  allow_all: '不做任何防护，所有工具调用直接放行',
  keyword_only: '只基于关键词进行简单拦截',
  gateway: '使用 AgentGuard 授权网关进行风险评分、策略判断和人工确认'
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
      <Section
        eyebrow="Independent Test Module"
        title="自动测试结果"
        description="读取 test/cases/gateway_cases*.json，输入 Gateway，自动生成 test/results/latest_* 结果。"
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
          <MetricCard
            title="测试样例"
            value={testSummary?.total_cases ?? 0}
            suffix=" cases"
            hint="本轮被读取并输入 Gateway 的样例数量"
            icon="lab"
          />
          <MetricCard
            title="通过样例"
            value={testSummary?.passed_cases ?? 0}
            suffix=" cases"
            hint="实际 decision 与 expected_decision 匹配的样例"
            icon="check"
          />
          <MetricCard
            title="失败样例"
            value={testSummary?.failed_cases ?? 0}
            suffix=" cases"
            hint="实际 decision 与预期不一致的样例"
            icon="shield"
          />
          <MetricCard
            title="准确率"
            value={formatPercentNumber(testSummary?.accuracy)}
            suffix="%"
            hint="passed_cases / total_cases"
            icon="spark"
          />
        </div>

        <div className="metric-grid compact">
          <MetricCard
            title="风险阻断/确认率"
            value={formatPercentNumber(testSummary?.risk_block_or_confirm_rate)}
            suffix="%"
            hint="风险样例被 confirm 或 deny 的比例"
            icon="shield"
          />
          <MetricCard
            title="风险误放行率"
            value={formatPercentNumber(testSummary?.risk_unsafe_allow_rate)}
            suffix="%"
            hint="风险样例被错误 allow 的比例"
            icon="arrow"
          />
          <MetricCard
            title="正常误拒率"
            value={formatPercentNumber(testSummary?.normal_false_deny_rate)}
            suffix="%"
            hint="正常样例被 deny 的比例"
            icon="dashboard"
          />
          <MetricCard
            title="平均延迟"
            value={testSummary?.avg_latency_ms ?? 0}
            suffix=" ms"
            hint="Gateway 判定平均耗时"
            icon="spark"
          />
        </div>

        <div className="matrix-grid">
          {renderDistribution('决策分布', testSummary?.decision_distribution)}
          {renderDistribution('类别分布', testSummary?.category_distribution)}
          {renderDistribution('工具分布', testSummary?.tool_distribution)}
        </div>

        <div className="code-panel">
          <strong>{latestTestAvailable ? '最新结果已生成' : '暂无最新结果'}</strong>
          <code>{testSummary?.generated_at ?? testSummary?.hint ?? '点击“一键运行测试”生成结果'}</code>
          <small>{testRunMessage ?? testSummary?.message ?? '按钮会调用后端 /test-results/run，并刷新 test/results/latest_summary.json。'}</small>
        </div>
      </Section>

      <Section
        eyebrow="Evaluation Lab"
        title="评测实验室"
        description="用于展示前端内置指标和后端评测指标。当前主数据源应以独立测试模块为准。"
        actions={<span className="status-pill">{latestTestAvailable ? '测试结果已同步' : '等待运行'}</span>}
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
        eyebrow="Strategy Comparison"
        title="旧策略横向对比"
        description="保留旧版 allow_all、keyword_only 与 gateway 对比展示。新评测入口已经迁移到上方独立测试模块。"
      >
        {strategyComparison?.available ? (
          <>
            <div className="metric-grid compact">
              <MetricCard
                title="测试样例"
                value={strategyComparison.total_cases}
                suffix=" cases"
                hint="参与评测的用例数量"
                icon="lab"
              />
              <MetricCard
                title="评测记录"
                value={strategyComparison.total_records}
                suffix=" rows"
                hint="策略与样例组合后的总记录数"
                icon="dashboard"
              />
              <MetricCard
                title="耗时"
                value={Number(strategyComparison.elapsed_ms.toFixed(2))}
                suffix=" ms"
                hint="本轮评测执行时间"
                icon="spark"
              />
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
            <strong>旧策略对比结果未接入</strong>
            <p>{strategyComparison?.hint ?? '当前推荐使用上方独立测试模块。'}</p>
          </div>
        )}
      </Section>

      <Section
        eyebrow="Test Case Matrix"
        title="测试用例矩阵"
        description="覆盖文件读取、邮件发送、Shell 命令、SQL 查询等典型 Agent 工具调用场景。"
      >
        <div className="matrix-grid">
          <div><strong>公开读取</strong><span>期望 allow 或 confirm</span></div>
          <div><strong>敏感读取</strong><span>期望 deny</span></div>
          <div><strong>外发邮件</strong><span>期望 confirm 或 deny</span></div>
          <div><strong>Shell 命令</strong><span>期望 confirm 或 deny</span></div>
          <div><strong>SQL 查询</strong><span>期望 confirm 或 deny</span></div>
          <div><strong>提示注入</strong><span>期望 confirm 或 deny</span></div>
        </div>
      </Section>

      <Section
        eyebrow="Result Files"
        title="结果文件"
        description={`当前独立测试结果${latestTestAvailable ? '已生成' : '未生成'}，耗时 ${formatMs(testSummary?.elapsed_ms)}。`}
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
    </div>
  );
}
