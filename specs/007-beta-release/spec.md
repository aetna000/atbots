# Stable publication — 2026-11-05

The owner now authorizes a stable release. Publish AtBots 0.3.1, including the
previously qualified Windows credential-storage fixes from 0969f30/ab68276.
Preserve legacy data and unrelated dirty development files. Stable distribution
does not mean every roadmap capability or provider is qualified. Existing
limitations remain explicit. Publish PyPI and a stable GitHub release after
cross-platform CI and installed-artifact gates pass. AtSys minimum is stable
0.3.2; AtMem remains compatible >=2.3.10,<3. Website publication is separately
owner-reviewed. The historical beta-only authorization below is superseded.

# AtBots 0.3.0b1 beta publication

## Corrective beta 0.3.0b2 — 2026-10-27

The owner requests publication of the UI-first corrections qualified in feature
006. Use version 0.3.0b2, retain the historical 0.3.0b1 evidence, and publish an
opt-in prerelease only. Preserve the original dirty checkout and all user data.
Include reusable provider connections, isolated agent memory/workspaces,
background UI, private AtSys setup, readable approvals and safe maintenance.
Cross-platform CI, source tests, wheel/sdist checks and clean installed-artifact
verification must pass before tagging. Verify GitHub and PyPI after publication.
No reinstall into user environments, website deployment, cloud provisioning,
stable-platform-complete claim or silent legacy removal is authorized.

User authorization: publish the next AtBot beta after AtSys 0.3.0b4.
Publish the standalone `atbots` distribution, not AtMem's legacy `atmem-atbot`.
Snapshot current feature-005/006 work into a separate release checkout, retain the
unrelated evaluation-baseline edit in the development checkout, and avoid live
credential changes, notifications, paid inference or cloud deployment.

Acceptance: dependency-conforming source tests and lint; wheel/sdist metadata;
clean installed-wheel imports, packaged web/container resources and named-agent
CLI smoke; CI on the reviewed commit; a versioned prerelease, registry files and
digests, and clean registry install. Describe experimental and unverified paths
accurately. Do not present full platform acceptance as complete.
