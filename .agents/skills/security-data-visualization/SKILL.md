\---

name: security-data-visualization

description: Improve visual representation of AgentGuard security data, including authorization decisions, risk levels, attack chains, audit hash chains, sandbox execution, benchmark metrics, evidence packages, and runtime monitor flows.

\---



\# Security Data Visualization Skill



You improve how security data is displayed in AgentGuard.



\## Security Concepts



The UI may display:

\- allow / confirm / deny authorization decisions

\- risk scores

\- capability contracts

\- semantic guard results

\- data-flow pollution

\- attack chains

\- sandbox execution

\- runtime monitor steps

\- audit hash chains

\- benchmark metrics

\- evidence packages



\## Visualization Goals



Make security results:

\- scannable

\- explainable

\- credible

\- judge-friendly

\- technically accurate



\## Status Mapping



Use consistent visual meaning:



\- allow / safe / passed: green

\- confirm / review / warning: amber

\- deny / blocked / high risk: red

\- running / live / monitoring: blue or cyan

\- unknown / unavailable: gray



\## Recommended UI Patterns



Authorization decision:

\- show decision badge

\- show reason

\- show matched policy

\- show risk level

\- show next action



Attack chain:

\- use step-by-step flow

\- show blocked step clearly

\- show data movement direction

\- show dangerous capability escalation



Audit hash chain:

\- show chain integrity status

\- show last hash

\- show event count

\- show verification result



Benchmark:

\- show key metrics first

\- use compact cards

\- show passed / failed / blocked counts

\- show comparison clearly

\- avoid misleading percentages



Evidence page:

\- show generation time

\- show file path or package name

\- show integrity status

\- show coverage summary

\- show reproducibility notes



\## Rules



Do not exaggerate security claims.

Do not invent metrics.

Do not hide failed or unknown states.

Do not remove technical details that support credibility.



\## Final Output



Summarize:

\- security concepts clarified

\- visualization improvements

\- files changed

\- any data limitations

