# 执行替换命令

在 `Agent-Authorization` 项目根目录执行：

```powershell
Expand-Archive -Force .\agent_authorization_test_module_restructure.zip -DestinationPath .
python .\apply_test_restructure.py
python -m test.run
```

如果压缩包在下载目录：

```powershell
Expand-Archive -Force "$env:USERPROFILE\Downloads\agent_authorization_test_module_restructure.zip" -DestinationPath .
python .\apply_test_restructure.py
python -m test.run
```

生成结果：

```text
test/results/latest_summary.json
test/results/latest_cases.json
test/results/latest_detail.csv
test/results/latest_report.md
test/results/latest_dashboard.html
```
