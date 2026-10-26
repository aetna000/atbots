"""Explicit operator commands equivalent to the conversational services."""

import argparse
import asyncio
import json
from pathlib import Path

from atbots.config import DEFAULT_ROOT
from atbots.platform.jobs import Operations
from atbots.platform.scheduler import Scheduler
from atbots.platform.store import AgentStore

COMMANDS = {
    "ui",
    "runner",
    "jobs",
    "schedules",
    "browser",
    "skills",
    "export",
    "import",
    "cloud",
    "memory",
    "doctor",
    "supervision",
    "state",
    "image-build",
}


def main(argv):
    parser = argparse.ArgumentParser(prog="atbots")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT / "platform")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    state = commands.add_parser("state")
    state.add_argument("action", choices=("export", "import"))
    state.add_argument("path", type=Path)
    state.add_argument("--name")
    state.add_argument("--key-env", default="ATBOTS_STATE_KEY")
    build = commands.add_parser("image-build")
    build.add_argument("--wheel", type=Path, required=True)
    build.add_argument("--image", required=True)
    build.add_argument("--base", required=True)
    build.add_argument("--approve", action="store_true")
    supervision = commands.add_parser("supervision")
    supervision.add_argument(
        "action",
        choices=("list", "status", "report", "pause", "resume", "stop", "amend"),
    )
    supervision.add_argument("id", nargs="?")
    supervision.add_argument("--objective")
    supervision.add_argument("--plan")
    ui = commands.add_parser("ui")
    ui.add_argument("--port", type=int, default=0)
    runner = commands.add_parser("runner")
    runner.add_argument("--once", action="store_true")
    jobs = commands.add_parser("jobs")
    actions = jobs.add_subparsers(dest="action", required=True)
    actions.add_parser("list")
    submit = actions.add_parser("submit")
    submit.add_argument("name")
    submit.add_argument("objective")
    submit.add_argument("--start", action="store_true")
    for action in ("show", "cancel", "pause", "resume"):
        item = actions.add_parser(action)
        item.add_argument("id")
    schedule = commands.add_parser("schedules")
    actions = schedule.add_subparsers(dest="action", required=True)
    actions.add_parser("list")
    item = actions.add_parser("create")
    item.add_argument("name")
    item.add_argument("objective")
    when = item.add_mutually_exclusive_group(required=True)
    when.add_argument("--at")
    when.add_argument("--cron")
    item.add_argument("--timezone", default="UTC")
    item.add_argument("--missed", choices=("skip", "catch_up_once"), default="skip")
    item.add_argument("--overlap", choices=("skip", "queue"), default="skip")
    for action in ("pause", "resume", "delete", "preview"):
        item = actions.add_parser(action)
        item.add_argument("id")
    browser = commands.add_parser("browser")
    browser.add_argument("name")
    browser.add_argument("--url")
    skills = commands.add_parser("skills")
    skills.add_argument("name")
    actions = skills.add_subparsers(dest="action", required=True)
    actions.add_parser("list")
    review = actions.add_parser("review")
    review.add_argument("source")
    install = actions.add_parser("install")
    install.add_argument("skill")
    install.add_argument("source")
    install.add_argument("digest")
    install.add_argument("--allow-code", action="store_true")
    export = commands.add_parser("export")
    export.add_argument("name")
    export.add_argument("--output", type=Path)
    im = commands.add_parser("import")
    im.add_argument("source", type=Path)
    im.add_argument("--allow-remote", action="store_true")
    cloud = commands.add_parser("cloud")
    cloud.add_argument(
        "action",
        choices=("plan", "deploy", "status", "run", "logs", "destroy", "stop", "stage"),
    )
    cloud.add_argument("--plan", type=Path, required=True)
    cloud.add_argument("--approve", action="store_true")
    cloud.add_argument("--execution")
    cloud.add_argument("--name")
    cloud.add_argument("--key-env", default="ATBOTS_STATE_KEY")
    memory = commands.add_parser("memory")
    memory.add_argument("name")
    actions = memory.add_subparsers(dest="action", required=True)
    actions.add_parser("list")
    for action in ("search", "remember"):
        item = actions.add_parser(action)
        item.add_argument("text")
    item = actions.add_parser("correct")
    item.add_argument("record")
    item.add_argument("text")
    item = actions.add_parser("forget")
    item.add_argument("record")
    for action in ("share", "revoke"):
        item = actions.add_parser(action)
        item.add_argument("recipient")
    args = parser.parse_args(argv)
    if args.command == "state" and args.action == "import":
        import os

        from atbots.platform.deployment import unpack_state

        key = os.environ.get(args.key_env)
        if not key:
            raise ValueError(
                "Provision the selected encryption-key environment reference"
            )
        restored = unpack_state(args.path.read_bytes(), args.root, key.encode())
        print(
            json.dumps(
                {
                    "root": str(restored.root),
                    "restored": True,
                    "browser_session_included": False,
                }
            )
        )
        return 0
    store = AgentStore(args.root)
    result = None
    if args.command == "doctor":
        from atbots.platform.doctor import doctor

        result = doctor(store)
    elif args.command == "image-build":
        from atbots.platform.deployment import build_container

        if not args.approve:
            raise PermissionError(
                "Registry build/push requires --approve; provider charges may apply"
            )
        result = build_container(args.wheel, args.image, args.base)
    elif args.command == "state":
        import os

        from atbots.platform.deployment import pack_state

        key = os.environ.get(args.key_env)
        if not key or not args.name:
            raise ValueError(
                "State export requires --name and a provisioned key environment reference"
            )
        payload = pack_state(store, args.name, key.encode())
        descriptor = os.open(args.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
        result = {
            "path": str(args.path),
            "encrypted": True,
            "browser_session_included": False,
        }
    elif args.command == "supervision":
        from atbots.platform.integrations import AtSysClient, Delegations

        registry = Delegations(store)
        if args.action == "list":
            result = registry.list()
        else:
            link = registry.get(args.id)
            client = AtSysClient(link["endpoint"])
            if args.action == "status":
                result = registry.observe(args.id)
            elif args.action == "report":
                result = client.report(link["upstream_id"])
            elif args.action == "amend":
                changes = {
                    key: value
                    for key, value in {
                        "objective": args.objective,
                        "plan": args.plan,
                    }.items()
                    if value is not None
                }
                if not changes:
                    raise ValueError("Supply --objective or --plan")
                result = client.amend(link["upstream_id"], changes)
            else:
                result = registry.action(args.id, args.action)
    elif args.command == "ui":
        from atbots.platform.web import serve

        serve(store, port=args.port)
        return 0
    if args.command == "runner":
        scheduler = Scheduler(store)
        if args.once:
            result = {"created": scheduler.tick(), "local_runner_required": True}
        else:
            scheduler.serve()
            return 0
    elif args.command == "jobs":
        ops = Operations(store)
        if args.action == "list":
            result = ops.list()
        elif args.action == "show":
            result = ops.get(args.id)
        elif args.action == "submit":
            result = ops.submit(args.name, args.objective)
            if args.start:
                result = ops.launch(result["id"])
        else:
            result = ops.action(args.id, args.action)
    elif args.command == "schedules":
        scheduler = Scheduler(store)
        if args.action == "list":
            result = scheduler.list()
        elif args.action == "create":
            result = scheduler.create(
                args.name,
                args.objective,
                at=args.at,
                cron=args.cron,
                zone=args.timezone,
                missed=args.missed,
                overlap=args.overlap,
            )
        elif args.action == "preview":
            result = scheduler.preview(args.id)
        else:
            result = scheduler.action(args.id, args.action)
    elif args.command == "browser":
        from atbots.platform.browser import BrowserTools

        caps = store.get(args.name).capabilities.model_copy(
            update={"browser_headed": True}
        )

        async def handoff():
            async with BrowserTools(
                store.workspace(args.name) / "browser", caps
            ) as browser:
                if args.url:
                    await browser.browser_navigate(args.url)
                await asyncio.to_thread(
                    input,
                    "Use this agent's browser to sign in. Press Enter here when finished; the isolated profile will be saved. ",
                )

        asyncio.run(handoff())
        return 0
    elif args.command == "skills":
        from atbots.platform.skills import Skills
        from atbots.platform.tools import WorkspaceTools

        manager = Skills(store.workspace(args.name) / "skills")
        if args.action == "list":
            result = manager.list_skills()
        else:
            source = WorkspaceTools(store.workspace(args.name) / "files").path(
                args.source
            )
            if args.action == "review":
                result = manager.review(str(source))
            else:
                result = manager.install(
                    args.skill, str(source), args.digest, allow_code=args.allow_code
                )
    elif args.command in {"export", "import"}:
        from atbots.platform.deployment import export_definition, import_definition

        if args.command == "import":
            result = import_definition(
                store,
                json.loads(args.source.read_text()),
                allow_remote=args.allow_remote,
            ).model_dump(mode="json")
        else:
            result = export_definition(store, args.name)
            if args.output:
                with args.output.open("x", encoding="utf-8") as stream:
                    json.dump(result, stream, ensure_ascii=False, indent=2)
    elif args.command == "cloud":
        from atbots.platform.deployment import CloudPlan, CloudRun

        plan = CloudPlan.model_validate_json(args.plan.read_text())
        adapter = CloudRun()
        if args.action == "plan":
            result = {
                "argv": adapter.command(plan, "deploy"),
                "applied": False,
                "cost": "Unknown; grant is not a provider hard billing cap",
            }
        elif args.action in {"status", "logs"}:
            result = adapter.apply(plan, args.action)
        elif not args.approve:
            raise PermissionError(
                "Cloud mutation requires --approve for this exact reviewed plan"
            )
        elif args.action == "stop":
            result = adapter.stop(plan, args.execution).returncode
        elif args.action == "stage":
            import os

            from atbots.platform.deployment import stage_cloud_state

            key = os.environ.get(args.key_env)
            if not key or not args.name:
                raise ValueError(
                    "Cloud stage needs --name and the provisioned state-key reference"
                )
            result = stage_cloud_state(store, args.name, plan, key.encode())
        else:
            result = adapter.apply(plan, args.action)
    elif args.command == "memory":
        from atbots.platform.memory import AtMemMemory

        memory = AtMemMemory(store, args.name)
        if args.action == "list":
            result = memory.inspect()
        elif args.action == "search":
            context = memory.context(args.text, egress="local")
            result = {
                "text": context.text,
                "receipt": memory.confirm(context, "operator-cli"),
            }
        else:
            with store.turn_lock(args.name):
                if args.action == "remember":
                    result = memory.remember(args.text)
                elif args.action == "correct":
                    result = memory.correct(args.record, args.text)
                elif args.action == "forget":
                    result = memory.forget(args.record)
                else:
                    result = store.share_memory(
                        args.name, args.recipient, enabled=args.action == "share"
                    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
