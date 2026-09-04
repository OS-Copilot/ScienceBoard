# Acceptance and test plan

The migration is complete only when every required gate below has direct
evidence.  A task receiving an incorrect model action is reported separately
from an environment/initializer/verifier error.

| Gate | Acceptance condition | Current evidence |
| --- | --- | --- |
| Source isolation | Original checkout code diff remains unchanged after the copy | Passing; `git diff --binary HEAD` SHA-256 remains `7c4e5d6be1d81d7a427c011df3a4a7da298caabcfe990a7f9757c9e04f4b146d` |
| Static Python/shell | All Python compiles, shell entrypoints parse, Compose renders | Passing |
| Unit tests | Docker/no-VMware selection, image safety label, manager lifecycle, parser and verifier regressions | 14/14 passing |
| Full verifier audit | Every bundled VM task and verifier is structurally checked | 169 tasks / 242 verifier entries / 0 structural errors |
| Image provenance | Rootfs archive checksum and required reference assets verified | Passing; 14,100,254,851-byte archive, SHA-256 recorded in progress log |
| Image build | `scienceboard:0.1` exists with amd64/version/flat-distribution metadata | Passing |
| Runtime API | Health, 1280x800 PNG, AT-SPI, execute, upload, read/write, recording | Passing; also launches VS Code and Firefox visibly, with Firefox discoverable and onboarding absent |
| Reset isolation | A file written in one container is absent after `revert` | Passing; reset also replaces the container and machine ID |
| Application coverage | All six app families initialize and expose verifier APIs | Passing; 6/6 initialized, 0 skipped |
| No-VMware runtime | Run with a deliberately failing `vmrun` first on `PATH` | Passing; all Docker tests completed |
| 20-task subset | Deterministic subset runs through every selected task | Passing; corrected result has 0 skips |
| Real agent outcome | Representative task passes using the configured key bank | Passing; final KAlgebra canary 1/1 |
| Cleanup | No labeled task containers remain after success/failure | Passing |

The deterministic subset is materialized by
`scripts/materialize_smoke_subset.py`.  It contains 20 tasks across all six
families and covers every published verifier kind: state/info/file, database,
equation/value/variable, Lean proof compilation, TeX compilation/content,
include patterns, and stop/ANS.

## Recorded runtime results

- `logs/key-bank-docker-smoke20-fixed`: full real-model run, 20 total,
  7 passed, 12 failed, 1 skipped. The skip exposed a ChimeraX closed-session
  exception; it was fixed to fail closed.
- `logs/key-bank-docker-chimerax-d03-fixed`: corrected D-03 rerun, ordinary
  failure with 0 skips. AlphaFold custom prediction redirected to a Google
  Colab sign-in page.
- Combining unique tasks after that corrective rerun: 7 passed, 13 failed,
  0 skipped.
- `logs/final-release-app6-init-final`: final-image deliberate debug/TIMEOUT initialization sweep,
  6 total and 0 skipped.
- `logs/key-bank-docker-final-release-canary`: final flattened release-image agent run,
  1 passed, 0 failed, 0 skipped.
- `logs/key-bank-docker-release-tex-b04` exposed a hidden Firefox desktop
  entry. After that was fixed,
  `logs/key-bank-docker-release-tex-b04-fixed` launched Firefox normally but
  exhausted the ten-step budget on first-run onboarding. Both behaviors now
  have deterministic runtime regression checks.
- `logs/key-bank-docker-final-release-tex-b04`: after both fixes, the model
  completed the Scholar/BibTeX/browser/clipboard path and pasted into
  TeXstudio. It used its tenth action without saving, so the file verifier
  returned an ordinary failure; 0 tasks skipped.

Agent task failures are not infrastructure failures: the logs show normal
observations/actions/verifier results. Acceptance requires no backend skip and
at least one genuine agent pass, not a 100% model score.
