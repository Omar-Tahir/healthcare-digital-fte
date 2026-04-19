# Skills — Index (ARCHIVED)

> **ARCHIVED:** These files are the source research documents.
> The active skills are now at `.claude/skills/`
> Each `.claude/skills/*/SKILL.md` was built from these sources.
> Update the `.claude/skills/` files when research is re-verified.

**Original purpose:** Domain knowledge documents that Claude reads before
working in each domain. Skills encode reusable knowledge from
the DISCOVER phase research into actionable reference guides.

Per Constitution Article I.5: domain knowledge lives in Skills,
not in prompts or agent code.

---

## Skill Status

| Skill | Domain | Status | Source Research |
|-------|--------|--------|----------------|
| icd10-coding-rules.md | ICD-10 coding | COMPLETE | DISC-001, DISC-002 |
| cdi-query-writing.md | CDI queries | COMPLETE | DISC-001, DISC-002, DESIGN-002 |
| drg-optimization.md | DRG impact | COMPLETE | DISC-002, DESIGN-001 |
| fhir-r4-integration.md | FHIR/EHR | COMPLETE | DISC-003, DESIGN-005 |
| payer-denial-patterns.md | Payer rules | COMPLETE | DISC-004 |
| hipaa-compliance.md | HIPAA/PHI | COMPLETE | Constitution II.4, ADR-005 |

---

## Skill Template

Each Skill follows this structure:

1. **Overview** — What this domain is and why it matters
2. **Key Rules** — The most important rules/constraints
3. **Examples** — Concrete examples of correct behavior
4. **Edge Cases** — Common mistakes and how to avoid them
5. **MCP Tool Usage** — When to call MCP tools vs use Skill knowledge

---

## When to Read a Skill

```
Before working on ICD-10 rules → Read icd10-coding-rules.md
Before working on CDI queries  → Read cdi-query-writing.md
Before working on DRG logic    → Read drg-optimization.md
Before working on FHIR client  → Read fhir-r4-integration.md
Before working on payer logic  → Read payer-denial-patterns.md
Before working on logging/PHI  → Read hipaa-compliance.md
```
