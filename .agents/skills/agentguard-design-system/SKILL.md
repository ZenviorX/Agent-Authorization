\---

name: agentguard-design-system

description: Create and maintain a consistent visual design system for the AgentGuard / Agent-Authorization project. Use this skill when unifying frontend HTML pages, CSS variables, colors, spacing, typography, cards, badges, buttons, tables, navigation, and dashboard styles.

\---



\# AgentGuard Design System Skill



You maintain the visual consistency of the AgentGuard project.



\## Project Goal



Create a unified security-product interface suitable for:

\- cybersecurity competition demonstration

\- AI Agent authorization gateway

\- audit dashboard

\- benchmark dashboard

\- evidence display pages

\- runtime security monitoring pages



\## Design Direction



The interface should feel:

\- professional

\- technical

\- credible

\- clean

\- security-oriented

\- suitable for judges and teachers



Avoid:

\- random colors across pages

\- inconsistent button styles

\- repeated inline CSS tokens with conflicting values

\- excessive decorative gradients

\- childish icons or cartoon style

\- overcomplicated nested cards



\## Core Visual Tokens



Prefer a restrained palette:

\- primary blue: security, system, control

\- cyan/teal: runtime, live, detection

\- green: allow, pass, safe

\- amber: confirm, warning, human review

\- red: deny, block, danger

\- gray: unknown, disabled, secondary



Use consistent:

\- border radius

\- card padding

\- table spacing

\- button height

\- heading size

\- muted text color

\- shadow strength



\## Workflow



1\. Inspect existing frontend HTML pages.

2\. Identify repeated CSS variables and component patterns.

3\. Unify naming and visual rules.

4\. If appropriate, extract shared CSS to `frontend/assets/agentguard.css`.

5\. Do not break existing page routes.

6\. Keep changes incremental and reviewable.



\## Component Standards



Cards:

\- use consistent padding

\- use subtle borders

\- avoid excessive nested borders

\- use clear section titles



Badges:

\- compact

\- color-coded by security meaning

\- readable on both light and dark backgrounds



Tables:

\- clear header

\- readable rows

\- horizontal scroll on small screens

\- no page-breaking overflow



Navigation:

\- current page should be visually obvious

\- spacing should be consistent

\- no unreadable hover state



\## Final Output



Always summarize:

\- style rules unified

\- files changed

\- components improved

\- remaining inconsistencies if any

