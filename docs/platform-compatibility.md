# Platform compatibility inventory

Feature 006 is additive and available as an opt-in beta, not a full-platform
completion claim. No existing API, command, configuration
or data directory has been removed in this implementation pass.

| Existing surface | Current behavior | Replacement / remaining migration |
| --- | --- | --- |
| `TaskAgent` and its custom task-step loop | Retained for existing callers and regression tests | New persistent agents use native Pydantic AI `AgentSession`; legacy loop migration remains a constitution/publication gate, not silently certified |
| `auth login/status/logout` | Retained; native profile/consent protection | Reused by named-agent providers; no token copying |
| `init/status/doctor/serve`, companion HTTP clients | Retained; old config and behavior untouched | New platform commands use named agents, `ui`, and explicit `--root PATH doctor`; eventual companion retirement needs impacted-consumer migration before removal |
| `~/.atbots/config.json`, old legacy root | Retained | Separate `~/.atbots/platform` registry; no implicit import or deletion |
| Legacy extraction/ranking providers | Retained for current companion clients | Still conflict with constitutional retired-surface policy; removal/replacement must be addressed before a platform release |
| AtMem databases | New per-agent scopes use public authority operations | No automatic backend-format conversion or canonical write bypass |
| Native model/toolset API | Actual Pydantic AI Agent exposed | Direct use bypasses AtBots session persistence/limits; trusted caller responsibility |
| AtSys existing installation/services | Not replaced | >=0.3.0b4 required by adapter; live old service upgrade must respect its managed tasks |
| Portable exports | Config only by default; encrypted private-state export is separate | No desktop keychains/browser profiles in general archives; explicit encrypted browser provisioning is a separate operator action |

The constitution's current removal policy and this preservation requirement are
not equivalent. Tests passing does not resolve that publication issue. The
feature convergence list records the remaining migration task explicitly.
