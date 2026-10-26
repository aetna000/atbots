# AtBots 0.3.0b1 beta publication

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
