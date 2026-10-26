# Release plan

For the 2026-10-27 correction use an isolated `release/0.3.0b2` worktree based
on public main 57046f3, overlay reviewed feature-006 files without the unrelated
eval baseline, and preserve existing publication workflow/history. Pin the
package/import/smoke-test version to 0.3.0b2, document exact UI-first install,
run local plus GitHub macOS/Linux/Windows gates, then push an immutable annotated
tag only on a reviewed clean commit. Trusted Publishing remains the publisher.
Check the registry's file digests and perform an independent registry install.

Use an isolated worktree based on the existing public main, with reviewed source,
authentication/platform specs and tests, excluding the dirty eval baseline.
Advance package and import versions to 0.3.0b1. Preserve legacy compatibility and
native Pydantic AI execution. Do not complete pending platform features as part
of a release-only pass. Add release notes and a tested tag-publishing workflow.
Run source, browser, metadata and installed-artifact gates before tagging; check
PyPI and GitHub after upload. Use existing publication authentication or Trusted
Publishing without exposing credentials. Missing external publisher registration
is a publication blocker, not a successful release.
