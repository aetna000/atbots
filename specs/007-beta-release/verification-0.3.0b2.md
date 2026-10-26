# AtBots 0.3.0b2 corrective beta verification

Branch `release/0.3.0b2` starts from public main `57046f3`. The source snapshot
excludes the user's unrelated `evals/baseline.json` change, retains old release
notes/workflows and does not modify the development checkout or user installs.

The package/import/test and installed-smoke versions are uniformly `0.3.0b2`.
Python >=3.11; compatibility bounds remain AtMem >=2.3.10,<3 and AtSys
>=0.3.0b4,<0.4. Public URLs and the UI-first guide are included. This is an
opt-in corrective beta, not full-platform or legacy-migration completion.

Before release preparation the development candidate passed 253 source tests,
181 installed tests, real Chrome desktop/mobile inspection, Copilot native
memory/environment/file calls, and real agent-proposal → private AtSys →
independently validated artifact and offline durable-report checks. Exact
development evidence, including failures, is retained in feature 006's
`corrective-verification-20261027.md`; its dev-version artifacts are not the
release artifacts.

Release-version wheel and sdist build locally. A separate pip environment
imports the installed 0.3.0b2 from site-packages, passes `pip check`, checks the
HTML/JS/CSS/built-in skill/container resources and executes a native TestModel
session plus actual CLI/version smoke. No user account login, paid inference,
notification, cloud provisioning or user-environment reinstall is part of this
publication pass.

Source-suite rerun, metadata validation, cross-platform CI and publication
receipts are recorded below once their results are verified. No tag is pushed
before required tests pass. Publication is not complete until registry files,
hashes, fresh install and GitHub prerelease have been checked.

## Release-version local gates

- macOS/Python 3.12.2 full suite: **253 passed, 6 opt-in evals deselected**,
  135.66 seconds. JUnit `/tmp/atbots-release-030b2-source.xml`.
- Wheel and source archive build successfully; Twine metadata checks both pass.
- Installed-wheel version/assets/native session/CLI smoke passes; `pip check`
  reports no broken requirements. JavaScript syntax, smoke-script import lint
  and `git diff --check` pass.
- Cross-platform CI and registry publication remain pending at this source
  checkpoint; no beta tag or publication success is inferred from these checks.
