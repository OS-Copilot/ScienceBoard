# Known issues and unresolved constraints

These items do not prevent Docker execution, but they affect portability,
reproducibility, or particular task outcomes.

| Area | Status and impact |
| --- | --- |
| ChimeraX redistribution | ChimeraX is present in the official environment. Review UCSF licensing before publishing a prebuilt image; use a private artifact channel by default. |
| ChimeraX D-03 / AlphaFold | In the acceptance run, custom prediction opened Google Colab and required a Google sign-in. An unattended benchmark cannot supply that account, so the task returned a normal failure. This is an upstream authentication dependency, not a Docker startup failure. |
| Web search tasks | Google Scholar and similar services can rate-limit, show CAPTCHAs, or change UI. TeXstudio B-04 therefore remains network/service dependent. |
| Firefox packaging | Ubuntu's Firefox package is a snapd shim, but containers do not run snapd. The build extracts the exact bundled Firefox 130 snap, installs a visible GNOME desktop entry, and uses a direct wrapper. A locked policy suppresses first-run onboarding. Activities discovery, a clean New Tab, visible startup, and `example.com` are covered by runtime smoke. |
| Rendering | The default uses Mesa llvmpipe. Functionality and resolution match, but pixels and performance are not guaranteed identical to VMware on a hardware GPU. |
| Architecture | Bundled binaries are amd64 only. ARM hosts require emulation or a separately rebuilt and revalidated environment. |
| Desktop plumbing | GNOME runs directly on Xvfb without GDM/systemd seats. Logs may contain harmless GDM, power-profile, portal, PipeWire, or FUSE warnings. Openbox is retained only as a GNOME startup fallback. |
| Image size | The reference environment produces a multi-gigabyte compressed archive and a larger local image. Plan artifact bandwidth and disk accordingly; see `image-delivery.md`. |
| Legacy apt source | The imported VM has an expired MiKTeX repository signing key. The Docker overlay disables that source before `apt-get update` and uses the already-installed TeX Live binaries for verification. |
| Trusted inputs | Task JSON can contain Python lambdas evaluated on the host, and the benchmark intentionally executes model-generated Python in the task container. Do not accept unreviewed task packs or expose the control service publicly. |
| Exact benchmark score | The acceptance model solved 7 of the selected 20 tasks. Remaining ordinary failures reflect model behavior, external services, or task difficulty; they are preserved in logs rather than relabeled as pipeline errors. |

The final distribution image is sanitized and flattened. Intermediate rootfs
and layered images are build inputs only and must not be distributed because
historical layers can retain deleted VM files. Sanitization removes SSH host
and user keys, persistent machine identity, shell histories, Git/GnuPG user
identity, browser profiles and caches, VS Code history/workspace databases,
desktop recent-file lists, application session metadata, audio/network cookies
and identifiers, system logs, and the source VM login keyring. Run
`scripts/audit_distribution.py` against the final image before distributing it.
