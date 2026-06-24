# Security Case Set

This directory stores structured security cases for Gateway evaluation.

Required fields:

- id
- category
- description
- request
- expected_decision or expected_decision_in

Decision meanings:

- allow: low-risk request can proceed.
- confirm: request has side effects or medium risk and requires review.
- deny: high-risk request should be blocked.
- review: legacy or external review state.

Run the local evaluation pipeline:

    .\scripts\run_project_evaluation.ps1
