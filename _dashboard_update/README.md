# AgentGuard Dashboard Update Pack

This pack replaces the current simple CI dashboard with the redesigned security evaluation dashboard.

## Files included

- `_dashboard_update/generate_ci_dashboard.py`
  - New dark security dashboard.
  - Adds Quality Gate.
  - Adds Security Score.
  - Adds Security Decision Matrix.
  - Adds Decision Distribution.
  - Adds Category Accuracy.
  - Adds Failed Cases First.
  - Adds searchable/filterable All Cases table.
  - Adds Methodology / How Calculated section.
  - Adds Raw Pytest Output collapsed section.
  - Generates both:
    - `Results/Result_XXX.html`
    - `Results/Result_XXX.json`

- `_dashboard_update/.ci.yml`
  - Uploads HTML and JSON artifacts.
  - Commits HTML and JSON back to `Results/` on push events.
  - Keeps `[skip ci]` to avoid infinite CI loops.

## Apply on Windows PowerShell

Run from repository root:

```powershell
Expand-Archive .\agentguard_dashboard_update_pack.zip -DestinationPath . -Force
.\_dashboard_update\apply_dashboard_update.ps1
python -m pytest tests -q
python tests/dashboard/generate_ci_dashboard.py
git status
git add .github/workflows/ci.yml tests/dashboard/generate_ci_dashboard.py Results
git commit -m "feat: redesign CI security dashboard"
git push origin main
```

## Apply on Git Bash / Linux / macOS

Run from repository root:

```bash
unzip -o agentguard_dashboard_update_pack.zip
bash _dashboard_update/apply_dashboard_update.sh
python -m pytest tests -q
python tests/dashboard/generate_ci_dashboard.py
git status
git add .github/workflows/ci.yml tests/dashboard/generate_ci_dashboard.py Results
git commit -m "feat: redesign CI security dashboard"
git push origin main
```

## Important

Do not ignore `Results/` in `.gitignore`.
The project requirement is to keep CI dashboard results in `Results/`.
