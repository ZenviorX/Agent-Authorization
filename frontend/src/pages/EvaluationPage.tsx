import type { EvaluationMetric, StrategyComparisonResponse } from '../types/domain';
import { MetricCard } from '../components/MetricCard';
import { Section } from '../components/Section';

function formatRate(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0.00%';
  return `${(value * 100).toFixed(2)}%`;
}

function formatMs(value?: number) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '0.00 ms';
  return `${value.toFixed(2)} ms`;
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
  strategyComparison
}: {
  metrics: EvaluationMetric[];
  strategyComparison: StrategyComparisonResponse | null;
}) {
  const summary = strategyComparison?.summary ?? {};
  const strategies = ['allow_all', 'keyword_only', 'gateway'].filter((name) => summary[name]);

  return (
    <div className="page-grid">
      <Section
        eyebrow="Evaluation Lab"
        title="评测实验室"
        description="用于展示不同授权策略在攻击样例和正常样例上的表现。"
        actions={<span className="status-pill">{strategyComparison?.available ? '结果已生成' : '等待运行'}</span>}
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
        title="策略横向对比"
        description="对比 allow_all、keyword_only 与 gateway 三种策略在安全样例中的表现。"
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

            <div className="code-panel">
              <strong>重新运行评测</strong>
              <code>.\scripts\run_strategy_comparison.ps1</code>
              <small>运行后会刷新 Results/strategy_comparison_* 文件。</small>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <strong>暂无策略对比结果</strong>
            <p>{strategyComparison?.hint ?? '请先运行 scripts/run_strategy_comparison.ps1。'}</p>
            <div className="code-panel">
              <code>.\scripts\run_strategy_comparison.ps1</code>
            </div>
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
        description={`当前评测结果${strategyComparison?.available ? '已生成' : '未生成'}，耗时 ${formatMs(strategyComparison?.elapsed_ms)}。`}
      >
        <div className="matrix-grid">
          <div><strong>CSV 文件</strong><span>{strategyComparison?.outputs?.csv ?? 'Results/strategy_comparison.csv'}</span></div>
          <div><strong>JSON 文件</strong><span>{strategyComparison?.outputs?.json ?? 'Results/strategy_comparison_summary.json'}</span></div>
          <div><strong>Markdown 报告</strong><span>{strategyComparison?.outputs?.markdown ?? 'Results/strategy_comparison_report.md'}</span></div>
          <div><strong>HTML 看板</strong><span>{strategyComparison?.outputs?.html ?? 'Results/strategy_comparison_dashboard.html'}</span></div>
        </div>
      </Section>
    </div>
  );
}
