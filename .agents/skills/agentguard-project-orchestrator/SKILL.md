\---

name: agentguard-project-orchestrator

description: Coordinate all AgentGuard / Agent-Authorization project work. Use this skill when the user asks to improve the whole project, optimize the frontend, prepare for cybersecurity competition, polish the demo, refactor project structure, improve policies, update dashboards, improve evidence pages, or make broad changes across frontend, backend, config, experiments, docs, and reports.

\---



\# AgentGuard Project Orchestrator Skill



You are working on the AgentGuard / Agent-Authorization project.



This is a cybersecurity competition and research prototype for AI Agent tool-call authorization, runtime monitoring, policy enforcement, attack-chain detection, sandbox execution, and tamper-evident audit evidence.



\## Core Project Identity



AgentGuard is not a generic admin dashboard.



It is an AI Agent security gateway and audit platform focused on:



\- external authorization for AI Agent tool calls

\- least-privilege capability contracts

\- deterministic policy checks

\- semantic risk detection

\- runtime monitoring

\- attack-chain detection

\- sandboxed execution

\- human confirmation for risky operations

\- tamper-evident audit logs

\- benchmark-based evaluation

\- evidence package generation

\- competition demonstration



\## Main Goal



When making changes, prioritize:



1\. Security correctness

2\. Explainability

3\. Competition presentation value

4\. Reproducibility

5\. Maintainability

6\. Visual polish



Do not prioritize visual decoration over security clarity.



\## Project Areas



\### Frontend



The frontend is mainly served from the `frontend/` directory as vanilla HTML, CSS, and JavaScript pages.



Use frontend-specific skills when appropriate:



\- Use `vanilla-security-dashboard-ui` for dashboard page visual improvements.

\- Use `agentguard-design-system` for cross-page style consistency.

\- Use `competition-showcase-ux` for showcase and judge-facing demo pages.

\- Use `security-data-visualization` for attack chains, audit chains, benchmark metrics, authorization decisions, and evidence views.



Do not introduce React, Vue, Vite, Tailwind, shadcn/ui, or a build system unless the user explicitly asks.



\### Backend



The backend is a FastAPI application.



When changing backend code:

\- preserve existing routes unless the user asks for route changes

\- avoid breaking frontend fetch calls

\- keep response schemas stable

\- maintain clear error messages

\- keep security checks explicit and auditable

\- add tests when practical



\### Config



The `config/` directory contains policy and semantic guard configuration.



When editing config:

\- preserve explainability

\- avoid over-broad allow rules

\- do not weaken security for convenience

\- keep deny rules explicit

\- document policy intent

\- check whether frontend labels or backend logic depend on config names



\### Experiments and Evidence



The project may contain benchmark results, generated evidence, audit logs, and reports.



When editing these areas:

\- do not invent metrics

\- do not fake benchmark improvements

\- distinguish real results from demo placeholders

\- preserve reproducibility

\- keep file paths and generation steps clear



\### Documentation



When editing README, reports, or presentation material:

\- explain the problem first

\- then explain AgentGuard's mechanism

\- then show demo route

\- then show evidence and benchmark value

\- avoid vague marketing claims

\- keep claims technically defensible



\## Decision Process



Before making broad changes:



1\. Identify which project area is affected:

&#x20;  - frontend

&#x20;  - backend

&#x20;  - config

&#x20;  - experiments

&#x20;  - evidence

&#x20;  - docs

&#x20;  - tests



2\. Identify the user intent:

&#x20;  - visual polish

&#x20;  - security improvement

&#x20;  - competition presentation

&#x20;  - bug fix

&#x20;  - architecture cleanup

&#x20;  - policy expansion

&#x20;  - report/documentation



3\. Choose the narrowest safe change.



4\. Preserve existing behavior unless the requested task requires behavior changes.



5\. Summarize:

&#x20;  - what was changed

&#x20;  - why it was changed

&#x20;  - what was preserved

&#x20;  - how to test or preview it



\## Safety Rules



Never:

\- remove security checks just to make demos pass

\- fake audit logs or benchmark numbers

\- hide failures without explanation

\- make broad architecture rewrites without need

\- add heavy frontend frameworks without explicit request

\- change public route paths accidentally

\- delete evidence or experiment outputs casually

\- weaken deny policies without documenting why



\## Competition Presentation Rules



For competition-facing pages and docs, emphasize:



\- Why AI Agent tool calls are risky

\- What authorization boundary AgentGuard adds

\- How the gateway decides allow / confirm / deny

\- How runtime monitoring catches multi-step risk

\- How semantic guard detects dangerous intent

\- How audit evidence proves what happened

\- How benchmark results show effectiveness



Use judge-friendly explanations, but keep technical accuracy.



\## Final Response Standard



After completing a task, report:



\- Files changed

\- Main improvements

\- Security impact

\- UI or documentation impact if relevant

\- How to run, preview, or test

\- Remaining risks or next recommended step

