# AtSys — built-in supervised execution

When the user says "AtSys, do this", "under supervision", or asks for a complex
goal requiring monitored execution, prepare a supervised objective rather than
pretending a chat response performed the work.

1. Inspect your environment and your agent's supervision configuration. Your
chat model and the configured worker/supervisor/repair models are separate.
2. Extract the goal, deliverables, measurable acceptance, scope and constraints.
Ask only for material missing information. Never invent a passing validator.
3. Use request_supervision to propose the objective using this agent's saved
role/permission profile. A setup-required response is not a running task.
4. The operator reviews the proposal and grants execution. Never approve your
own proposal, broaden permissions, or substitute another agent's workspace.
5. After approval inspect supervision_tasks for your own returned correlation
ID. Upstream AtSys owns worker, observers, supervisor, repair and recovery.
6. Completion needs a real upstream report and declared-validator evidence.
Worker replies, progress, a process exit and a proposed task are not equivalent
to verified completion. Preserve partial failures and unknown cost.

Do not start nested AtSys work if already acting as its worker, supervisor or
repair agent. Keep unrelated work, credentials and other agents' memory private.
An uncertain external side effect must be reconciled before retrying. Missing
CLI, authorization or service access leads to actionable setup, not blind replay.
