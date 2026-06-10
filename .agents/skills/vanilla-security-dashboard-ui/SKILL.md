\---

name: vanilla-security-dashboard-ui

description: Improve the AgentGuard frontend dashboard built with vanilla HTML, CSS, and JavaScript. Use this skill when editing frontend/\*.html pages, security dashboards, benchmark pages, audit views, evidence pages, showcase pages, cards, tables, badges, layout, colors, responsive behavior, and visual polish. Do not introduce React, Vue, Tailwind, or build tools unless explicitly requested.

\---



\# Vanilla Security Dashboard UI Skill



You are improving the AgentGuard frontend.



\## Project Context



This project uses FastAPI to serve vanilla HTML dashboard pages from the `frontend/` directory.



The frontend is mainly:

\- HTML files

\- inline or shared CSS

\- vanilla JavaScript

\- fetch calls to FastAPI endpoints

\- security dashboard pages

\- benchmark result pages

\- evidence and audit pages

\- competition showcase pages



Do not convert the frontend to React, Vue, Vite, Next.js, Tailwind, or shadcn/ui unless the user explicitly asks.



\## Goals



Improve the UI while preserving existing backend routes and JavaScript behavior.



Prioritize:

\- professional security dashboard style

\- clear visual hierarchy

\- consistent spacing

\- readable tables

\- meaningful status badges

\- better cards and panels

\- responsive layout

\- good contrast

\- competition presentation quality



\## Workflow



1\. Inspect the target HTML file first.

2\. Identify existing CSS variables, layout classes, cards, buttons, tables, and scripts.

3\. Preserve all API endpoints and existing JavaScript logic unless fixing a bug.

4\. Improve the visual structure first:

&#x20;  - header

&#x20;  - navigation

&#x20;  - metric cards

&#x20;  - main content grid

&#x20;  - tables

&#x20;  - status sections

&#x20;  - empty/error states

5\. Avoid unnecessary dependencies.

6\. After editing, summarize:

&#x20;  - files changed

&#x20;  - visual improvements

&#x20;  - preserved behavior

&#x20;  - how to preview the page



\## Design Rules



Use a serious security-console style:

\- clean background

\- restrained color palette

\- clear status colors

\- compact but readable cards

\- strong section titles

\- subtle borders

\- subtle shadows

\- no excessive gradients

\- no cartoonish UI



For status:

\- allow = green

\- confirm = amber/orange

\- deny = red

\- unknown = gray

\- running/live = blue or cyan



For tables:

\- keep headers clear

\- use subtle row separators

\- prevent overflow

\- support horizontal scroll on small screens

\- avoid tiny text



For code or JSON:

\- use monospace

\- preserve whitespace

\- allow wrapping or scrolling

\- avoid breaking page width



\## Final Check



Before finishing:

\- no black text on dark background

\- no unreadable low-contrast text

\- no broken mobile layout

\- no unused code if obvious

\- no changed backend route names

\- no removed important content

