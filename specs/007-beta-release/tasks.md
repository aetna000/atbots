# Stable publication tasks — 2026-11-05

- [x] Isolate main and incorporate the two qualified Windows credential fixes.
- [x] Align 0.3.1 versions, stable AtSys minimum and current documentation.
- [ ] Pass cross-platform source and Windows credential gates.
- [ ] Pass wheel/sdist metadata and installed-artifact smoke.
- [ ] Merge reviewed PR, tag, publish and verify PyPI/GitHub stable release.
- [ ] Prepare the separate website PR for owner merge.

# Release tasks

## Corrective 0.3.0b2 publication

- [x] Isolate the release snapshot and preserve unrelated development changes.
- [x] Set one 0.3.0b2 version and update UI-first notes/guides/installed smoke.
- [x] Pass corrective release source, build, metadata and installed-wheel gates.
- [ ] Push reviewed release commit and pass the full cross-platform CI matrix.
- [ ] Push immutable annotated v0.3.0b2 tag, verify publisher, GitHub prerelease,
      PyPI hashes and a fresh registry install; record publication receipts.

- [x] Snapshot release scope while preserving unrelated development changes.
- [x] Set 0.3.0b1 versions and write release scope/limitations.
- [x] Pass source, browser, lint, build and metadata gates.
- [x] Verify clean installed wheel and bundled resources.
- [ ] Push reviewed release commit and pass CI.
- [ ] Tag, publish, verify registry hashes and fresh install; create prerelease.
