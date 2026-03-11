"""Policy Inheritance and Overlay Implementation (REQ-1.5)

## Design Summary

Attest implements policy inheritance through **overlay composition**. An overlay is a partial profile 
that merges into a base profile, replacing or extending controls and metadata.

## Overlay Semantics

- **Identity is preserved**: The base profile's name and version are retained in the merged result.
- **Controls merge by ID**: An overlay control with matching ID replaces the base control; 
  controls without a match in overlay are preserved; overlay controls without base are appended.
- **Deterministic ordering**: Controls are sorted by ID after merge for diff-friendly reports.
- **Metadata merging**: Inputs and dependencies merge, with overlay values taking precedence 
  for conflicting names.

## Use Cases

1. **Company policies from national baselines**: A company can overlay its organisational requirements
   onto CIS or NIST hardening guidance.
2. **Environment variants**: Dev/staging/production overlays can refine controls specific to each deployment.
3. **Compliance stacking**: A baseline profile can be overlaid with industry-specific requirements 
   (e.g., HIPAA, PCI-DSS).

## Resolver Interface

`OverlayResolver` provides two main methods:

- `resolve_overlay(base_profile, base_controls, overlay_profile, overlay_controls)` → 
  (merged_profile, merged_controls)
- `apply_overlays(base_profile, base_controls, overlays: list[...])` → (merged_profile, merged_controls)

The resolver ensures that overlay chains are applied in sequence, with each result feeding into the next.

## Example

A base NIST hardening profile can be overlaid with a company security policy:

```python
from attest.policy.overlay import OverlayResolver

resolver = OverlayResolver()

# Load base profile (e.g., NIST)
nist_profile, nist_controls = load_profile("nist-800-53")

# Load company overlay
company_overlay, company_controls = load_profile("acme-security-policy")

# Merge
merged, merged_controls = resolver.resolve_overlay(
    nist_profile, nist_controls,
    company_overlay, company_controls
)

# The merged profile keeps NIST's name and version, 
# with controls overlaid by the company policy.
```

## Integration Points

- **Policy loader** (`src/attest/policy/loader.py`): Resolves overlay dependencies and chains them.
- **CLI validate/run**: Profiles can reference their overlays via `depends[].overlay = true`.
- **Reports**: Provenances track which overlays were applied and in what order.
"""
