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
  gateway: 'Gateway'
};

const strategyDescriptions: Record<string, string> = {
  allow_all: '???????????????????',
  keyword_only: '???????????????????',
  gateway: '??????????????????????????'
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
        title="????"
        description="??????????????????????????????????"
        actions={<span className="status-pill">{strategyComparison?.available ? '?????' : '??????'}</span>}
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
        title="???????"
        description="??????????? allow_all?keyword_only ? gateway ???????????"
      >
        {strategyComparison?.available ? (
          <>
            <div className="metric-grid compact">
              <MetricCard
                title="????"
                value={strategyComparison.total_cases}
                suffix=" cases"
                hint="???????????????"
                icon="lab"
              />
              <MetricCard
                title="????"
                value={strategyComparison.total_records}
                suffix=" rows"
                hint="???? ? ?????"
                icon="dashboard"
              />
              <MetricCard
                title="????"
                value={Number(strategyComparison.elapsed_ms.toFixed(2))}
                suffix=" ms"
                hint="???????????"
                icon="spark"
              />
            </div>

            <div className="matrix-grid">
              {strategies.map((name) => {
                const item = summary[name];
                return (
                  <div key={name}>
                    <strong>{strategyNames[name] ?? name}</strong>
                    <span>{strategyDescriptions[name] ?? '??????'}</span>
                    <span>????/????{formatRate(item.attack_block_or_confirm_rate)}</span>
                    <span>???????{formatRate(item.attack_allow_rate)}</span>
                    <span>???????{formatRate(item.normal_not_denied_rate)}</span>
                    <span>??????{formatRate(item.decision_match_rate)}</span>
                  </div>
                );
              })}
            </div>

            <div className="code-panel">
              <strong>??????</strong>
              <code>.\scripts\run_strategy_comparison.ps1</code>
              <small>???????? Results/strategy_comparison_*?</small>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <strong>???????????</strong>
            <p>{strategyComparison?.hint ?? '??????? scripts/run_strategy_comparison.ps1?'}</p>
            <div className="code-panel">
              <code>.\scripts\run_strategy_comparison.ps1</code>
            </div>
          </div>
        )}
      </Section>

      <Section
        eyebrow="Test Case Matrix"
        title="??????"
        description="????????????????????????????SQL ??????????????????"
      >
        <div className="matrix-grid">
          <div><strong>??????</strong><span>?? allow ? confirm</span></div>
          <div><strong>????</strong><span>?? deny</span></div>
          <div><strong>????</strong><span>?? confirm ? deny</span></div>
          <div><strong>Shell ????</strong><span>?? confirm ? deny</span></div>
          <div><strong>SQL ??</strong><span>?? confirm ? deny</span></div>
          <div><strong>????</strong><span>?? confirm ? deny</span></div>
        </div>
      </Section>

      <Section
        eyebrow="Result Files"
        title="??????"
        description={`???????${strategyComparison?.available ? '???' : '???'}??? ${formatMs(strategyComparison?.elapsed_ms)}?`}
      >
        <div className="matrix-grid">
          <div><strong>CSV ??</strong><span>{strategyComparison?.outputs?.csv ?? 'Results/strategy_comparison.csv'}</span></div>
          <div><strong>JSON ??</strong><span>{strategyComparison?.outputs?.json ?? 'Results/strategy_comparison_summary.json'}</span></div>
          <div><strong>Markdown ??</strong><span>{strategyComparison?.outputs?.markdown ?? 'Results/strategy_comparison_report.md'}</span></div>
          <div><strong>HTML ???</strong><span>{strategyComparison?.outputs?.html ?? 'Results/strategy_comparison_dashboard.html'}</span></div>
        </div>
      </Section>
    </div>
  );
}
