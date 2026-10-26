# Release plan

Use an isolated worktree based on the existing public main, with reviewed source,
authentication/platform specs and tests, excluding the dirty eval baseline.
Advance package and import versions to 0.3.0b1. Preserve legacy compatibility and
native Pydantic AI execution. Do not complete pending platform features as part
of a release-only pass. Add release notes and a tested tag-publishing workflow.
Run source, browser, metadata and installed-artifact gates before tagging; check
PyPI and GitHub after upload. Use existing publication authentication or Trusted
Publishing without exposing credentials. Missing external publisher registration
is a publication blocker, not a successful release.
