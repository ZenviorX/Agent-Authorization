# Agent Authorization Gateway 安全评测报告 V2

## 1. 总体结果

- 总样例数：70
- 通过样例数：70
- 总体一致率：100.00%
- 平均检测延迟：0.120 ms

## 2. 攻击拦截能力

- 攻击样例数：49
- 攻击阻断/升级确认率：100.00%
- 攻击误放行率：0.00%

## 3. 正常任务可用性

- 正常样例数：15
- 正常任务放行/确认率：100.00%
- 正常任务误拒绝率：0.00%

## 4. 样例文件分布

- gateway_cases.json: 30
- gateway_cases_v2.json: 10
- gateway_cases_v3.json: 30

## 5. 决策分布

- allow: 5
- confirm: 34
- deny: 31

## 6. 分类分布

- normal: 15
- attack: 49
- suspicious: 6

## 7. 分类准确率

- normal: 15/15，100.00%
- attack: 49/49，100.00%
- suspicious: 6/6，100.00%

## 8. 失败样例

无失败样例。
