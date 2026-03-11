# Attest Agent Usage Matrix

Use this matrix to choose the right agent quickly for Attest work.

| Task type | Primary agent | Use when | Output expectation |
| --- | --- | --- | --- |
| Architecture alignment | Attest Architecture | You need a fit/conflict decision against layer boundaries or requirements | Decision, rationale, required changes, documentation impact |
| Quality and security review | Attest Assurance | You need risk findings, quality-gate coverage, or release readiness checks | Findings by severity, residual risks, suggested verification |
| Python implementation | Attest Python Implementer | You are implementing or refactoring Python behaviour and tests | Code changes, architecture fit, REQ traceability, verification |
| Fast exploration and discovery | Explore | You need read-only codebase discovery, symbol hunting, or quick context gathering | Concise findings and file locations |

## Typical Routing

1. Start with Explore for quick context.
2. Use Attest Architecture if layering or placement is unclear.
3. Use Attest Python Implementer to make code changes.
4. Use Attest Assurance before merge for risk-focused review.

## Notes

- Keep recommendations honest to Attest's bootstrap maturity.
- Preserve four-layer contracts: policy, resource, engine, and reporting.
- Keep requirement traceability explicit for substantial changes.