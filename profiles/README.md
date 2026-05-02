# Profile catalog — MLR Precheck v1

Each profile YAML in this folder declares a *compliance scope*: what
asset shape it applies to (market × doc_type × audience), which rules
activate (cascade + precheck dependency), which rules Atlas may
auto-insert canonical blocks for, and per-rule parameter overrides
(approval-code regex, AE-reporting authority, date freshness, …).

The precheck engine reads a single profile per asset and uses it to:

1. Decide which **cascade rules** to fire (`cascade_rules.{pillar}` lists)
2. Decide which **precheck dependency rules** to evaluate (`precheck_dependency_rules.{pillar}`)
3. Tighten parameters via `rule_overrides`
4. Decide which findings can be **auto-inserted** without human review (`auto_insert_allowed`)

Profile selection (per `MLR_PRECHECK_API.md` §3.1) is metadata-driven —
brand + market + doc_type from the email composer or Atlas extraction
form. When metadata is incomplete the API returns `422 profile_required`
and the UI prompts the user to pick from this catalog.

## v1 catalog

| Profile id                       | Market | Doc type | v1 active | Used by                                 |
|----------------------------------|--------|----------|-----------|-----------------------------------------|
| `UK-Branded-Promotional`         | UK     | email    | ✓         | First 20–30 approved UK emails (corpus) |
| `IE-Branded-Promotional`         | IE     | email    | drafted   | Inactive until IE corpus comes online   |
| `Event-Promotional`              | UK     | email    | ✓         | Jakavi-style event invitations          |
| `Non-Branded-Disease-Awareness`  | UK     | email    | drafted   | Disease education without brand mention |

## Rule namespaces

To keep cascade rules and precheck dependency rules unambiguous when
both engines reference them in the same profile, the YAMLs prefix every
list:

- `cascade_rules.{pillar}` → ids defined in `OBLIGATION_CASCADE_SPEC.md` §6
- `precheck_dependency_rules.{pillar}` → ids defined in `dependency_rules.yaml`

Some ids appear under both namespaces (e.g. `r_abbreviations_defined`
exists as both a cascade rule and a precheck rule). The two engines
treat them as independent: the cascade fires it as a structural
obligation; the precheck fires it conditionally on detected acronyms.
The X-Ray UI shows both verdicts side-by-side with their `layer` so
reviewers see exactly which engine produced each finding.

## Per-customer overrides (deferred to v1.5)

When ≥3 customers go live in the same market, fork the profile into
`<profile_id>.<customer>.yaml` (e.g. `UK-Branded-Promotional.novartis.yaml`)
with the same schema. The engine merges the customer override over the
base profile by rule id; missing keys inherit from base.

## Adding a new profile

1. Copy the closest existing profile.
2. Update `id`, `market`, `description`, `detection`.
3. Prune `cascade_rules` / `precheck_dependency_rules` to only those
   that apply.
4. Update `rule_overrides` for any market/MAH-specific parameters
   (approval-code regex, AE authority, freshness windows).
5. Set `status.v1_active: false` until the corpus is large enough to
   support the rule's coverage minimums.
6. Run `python -m src.mlr.precheck.profiles validate` to check id
   references resolve.

## Schema versioning

Every profile carries `schema_version: "1.0"`. The engine refuses to
load a profile with an unknown major version. Additive minor changes
(new optional fields) bump minor only.
