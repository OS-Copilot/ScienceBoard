# Verifier audit

## Scope

The VM set currently contains 169 tasks:

| Family | Tasks | Verifier kinds observed |
| --- | ---: | --- |
| Celestia | 33 | `info`, `stop` |
| ChimeraX | 29 | `states`, `file`, `info`, `stop` |
| GrassGIS | 34 | `info`, `db`, `stop` |
| KAlgebra | 31 | `eqn`, `val`, `var`, `stop` |
| Lean | 26 | `placeholder` |
| TeXstudio | 16 | `compile`, `file`, `include`, `stop` |

## Audit method

Each verifier will be checked for:

1. soundness: passing implies the requested state was achieved;
2. completeness: equivalent correct states are not rejected needlessly;
3. determinism and tolerance: no accidental dependence on rendering, order,
   timing, network, or floating-point exact equality;
4. isolation: it reads only state produced inside the current task container;
5. failure behavior: missing/malformed state fails rather than passing or
   crashing the whole run;
6. instruction alignment: keys, constants, paths, and units match the task.

The executable audit is `scripts/audit_verifiers.py`.  It loaded all 169 task
files and checked all 242 verifier entries, initializer relationships, lambda
and regular-expression syntax, stop/ANS metadata, TeX replacement uniqueness,
and app-specific required fields.  The current result is zero structural
errors.

```bash
python scripts/audit_verifiers.py
python scripts/audit_verifiers.py .artifacts/smoke20
```

## Findings and fixes

| ID | Severity | Finding | Resolution |
| --- | --- | --- | --- |
| VER-001 | High | ChimeraX `states` checks using `find` plus `value: null` referenced an unbound `raw_keys`, so the verifier silently returned false through `error_factory`. | Fixed to build and check the actual matched-key list; regression test added. |
| VER-002 | High | A direct ChimeraX state key with `value: null` checked `None not in current_states`, which was vacuously true even when the requested key existed. | Fixed direct-key absence semantics; regression test added. |
| VER-003 | Medium | ChimeraX `find` selected only the first matching serialized key. Multiple valid candidates made the result insertion-order dependent. | Evaluate all transformed matching keys and accept when any candidate satisfies the expected value/pattern. |
| VER-004 | Medium | ChimeraX `info` converted output to sets, allowing a duplicate expected line and a missing distinct line to compare equal. | Compare sorted lists, preserving multiplicity while remaining order-independent. |
| VER-005 | Medium | The Lean checker searched only stdout for `sorry`; tool versions may emit the warning on stderr. It also had no build timeout. | Check combined stdout/stderr and fail closed after 300 seconds. |
| VER-006 | Medium | TeX compilation could wait indefinitely for interactive input on malformed input/missing files. | Use `-interaction=nonstopmode -halt-on-error`, null stdin, a 180-second timeout, and fail closed on process errors. |
| VER-007 | High | Closing or losing ChimeraX made its state endpoint return non-JSON and raised through evaluation, causing an infrastructure-looking skip. | Catch unavailable or malformed application state and return a normal failed verification. |
| VER-008 | High | A fenced primitive such as `ANS 109.03` lost its first line because the parser treated it as a language tag. | Strip an opening language tag only when it is the complete first line; regression tests cover `ANS value` and `WAIT n`. |

These changes preserve the intended success conditions and only remove false
positives, false negatives, ordering dependence, or indefinite hangs.

## Remaining limitations

- Official task JSON is trusted input. Celestia, GrassGIS, and ChimeraX use
  task-authored Python lambdas for selectors/predicates on the host. This is
  acceptable for the bundled suite but unsafe for unreviewed third-party task
  packs.
- Several ChimeraX checks compare serialized private object fields (including
  large render arrays). They are necessarily tied to ChimeraX 1.9 and the
  bundled `chimerax-states` plugin. The parity image retains those exact
  versions; a package upgrade requires re-auditing them.
- ChimeraX D-03 checks that an AlphaFold log contains the host's current date.
  This can be timezone-sensitive close to midnight and depends on a live
  external prediction service. It remains unchanged to avoid altering the
  published benchmark definition; the 20-task report must distinguish a
  network/service failure from a Docker backend failure.
- Stop/ANS metadata is internally consistent for every task with an `ans`
  field. The scientific truth of all 32 answer strings still ultimately
  depends on the fixed reference datasets. Representative answers are covered
  by runtime tests; this audit does not claim an independent reconstruction of
  every source dataset.
