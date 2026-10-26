# AtBots 0.3.0b1 release candidate verification

Isolated release branch: release/0.3.0b1, based on public main 28f5551.
Copied the reviewed feature-005/006 source, docs/specs and tests; the original
checkout and its dirty evals/baseline.json were not changed. Original platform
tasks remain open; this beta does not claim full platform acceptance.

Local macOS/Python 3.12 checks: 187 source tests passed, six opt-in live-model
evaluations deselected. After the version/docs-only release updates, package
version and full web test subset passed seven tests, including actual desktop
and mobile browser checks. Auth/platform source and tests plus the new installed
smoke script pass Ruff. Wheel and source distribution build and pass Twine.
A clean base-only wheel install outside source imports passed version/resource
checks, a native Pydantic AI TestModel agent session and actual named-agent CLI
listing. Dependency consistency passed. HTML and container resources are packaged.
No real account login, paid model, notification or cloud provisioning was used.

PyPI authentication preflight found no inherited publishing token, no repository
publishing secret, and no saved PyPI token in the native system keychain. This
repository has no existing tag publisher. A reviewed GitHub OIDC workflow is
provided as .github/workflows/publish.yml, environment pypi, project atbots.
Publication must still prove the registry accepts that identity; a pushed branch
or version bump alone is not a completed release.

Release notes: docs/releases/v0.3.0b1.md. Local logs and distributions are in
ignored dist/release-evidence and dist/packages. The published artifact must
be verified independently against its registry digest and a clean install.

Initial Linux/Python 3.12 CI passed. Python 3.10 correctly exposed an impossible
dependency resolution: pydantic-ai-slim 2.61 requires Python >=3.11. The beta
metadata, migration notes and minimum-version CI target now declare 3.11. This
changes the supported minimum honestly rather than downgrading authentication
code to an unverified upstream version. Superseded branch runs are cancelled
when a new commit replaces them; current full-platform checks still run.
