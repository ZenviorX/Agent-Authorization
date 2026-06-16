import type { EvaluationMetric } from '../types/domain';
import { MetricCard } from '../components/MetricCard';
import { Section } from '../components/Section';

export function EvaluationPage({ metrics }: { metrics: EvaluationMetric[] }) {
  return (
    <div className="page-grid">
      <Section
        eyebrow="Evaluation Lab"
        title="效果评测"
        description="适合把实验里的 100 轮测试、攻击拦截率、误拦率和耗时统计展示出来。"
        actions={<button className="primary-btn small">运行测试</button>}
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

      <Section eyebrow="Test Cases" title="建议测试用例矩阵" description="答辩时可以说明你们不是只做 UI，而是有安全验证闭环。">
        <div className="matrix-grid">
          <div><strong>正常公开读取</strong><span>预期 allow</span></div>
          <div><strong>路径穿越</strong><span>预期 deny</span></div>
          <div><strong>删除文件</strong><span>预期 confirm</span></div>
          <div><strong>Shell 高危命令</strong><span>预期 deny</span></div>
          <div><strong>订单提交</strong><span>预期 confirm</span></div>
          <div><strong>策略修改</strong><span>预期 review</span></div>
        </div>
      </Section>
    </div>
  );
}
