# ADR-004: Deterministic Analyzer Before LLM

## Status

Accepted

## Context

Repository analysis can be done deterministically (file detection, dependency parsing) or with LLM-based analysis (understanding intent, inferring framework from code patterns). We need to decide which approach to implement first.

## Decision

Implement deterministic analysis first, with LLM-based analysis as a future enhancement. The deterministic analyzer provides a reliable baseline that can be validated and tested.

## Consequences

**Positive:**
- Deterministic results — same repo always produces same analysis
- Fast execution — no API calls to LLM providers
- Testable — can validate against known repositories
- No cost per analysis
- Reliable baseline for comparison

**Negative:**
- Cannot handle ambiguous repositories
- Limited to pattern matching (file names, dependency lists)
- May miss frameworks with unconventional structure
- Cannot infer intent or purpose

## Implementation

The deterministic analyzer uses:
1. File presence detection (package.json, requirements.txt, etc.)
2. Dependency name matching (flask, django, next, etc.)
3. Configuration file parsing
4. Entry point detection

Confidence scores reflect detection certainty:
- 0.9+ — Strong match (framework dependency + config file)
- 0.5-0.9 — Moderate match (partial evidence)
- <0.5 — Weak match (fallback detection)

## Future LLM Integration

Phase 2+ can add LLM analysis for:
- Ambiguous repositories
- Custom frameworks
- Code pattern understanding
- Build command inference
- Environment variable detection

The deterministic analyzer remains as the fast path, with LLM analysis as an optional enhancement.
