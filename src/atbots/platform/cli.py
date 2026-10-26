"""Terminal client for named agents and conversational management."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from atbots.config import DEFAULT_ROOT
from atbots.platform.models import ModelBinding
from atbots.platform.session import AgentSession
from atbots.platform.store import AgentStore


def _options(parser):
    parser.add_argument(
        "--provider",
        choices=(
            "ollama",
            "openai-compatible",
            "chatgpt",
            "github-copilot",
            "anthropic",
        ),
    )
    parser.add_argument("--model")
    parser.add_argument("--endpoint")
    parser.add_argument("--api-key-env")
    parser.add_argument("--auth-profile")
    parser.add_argument("--instructions")
    remote = parser.add_mutually_exclusive_group()
    remote.add_argument("--allow-remote", action="store_true", default=None)
    remote.add_argument("--deny-remote", action="store_true", default=None)


def _binding(args, old=None):
    values = (old or ModelBinding()).model_dump()
    for arg, field in (
        ("provider", "kind"),
        ("model", "model"),
        ("endpoint", "endpoint"),
        ("api_key_env", "api_key_env"),
        ("auth_profile", "auth_profile"),
    ):
        value = getattr(args, arg, None)
        if value is not None:
            values[field] = value
    if args.allow_remote:
        values["egress_class"] = "remote"
    if args.deny_remote:
        values["egress_class"] = "local"
    return ModelBinding.model_validate(values)


def _show(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _chat(store, name, message=None):
    session = AgentSession(store, name)
    if message is not None:
        result = session.chat(message)
        print(f"{name}> {result.text}")
        return
    print(
        f"Agent: {name}. /exit returns to your terminal. No background work is started by this chat."
    )
    while True:
        try:
            prompt = input("you> ")
        except EOFError:
            return
        if prompt.strip() in {"/exit", "/quit"}:
            return
        if prompt.strip():
            print(f"{name}> {session.chat(prompt).text}")


def _control(store):
    from atbots.platform.control import ControlRoom

    room = ControlRoom(store)
    print(
        "AtBots control room. Configure its model with 'agents configure control-room' if needed. /exit to leave."
    )
    while True:
        try:
            prompt = input("you> ")
        except EOFError:
            return
        if prompt.strip() in {"/exit", "/quit"}:
            return
        if not prompt.strip():
            continue
        try:
            value = room.dispatch(room.plan(prompt))
            _show(value)
            if "approval_required" in value:
                answer = input("Apply this exact operation? [y/N] ")
                if answer.strip().lower() == "y":
                    _show(room.approve(value["approval_required"]))
                else:
                    room.reject(value["approval_required"])
                    print("control-room> Not applied.")
        except (ValueError, RuntimeError) as exc:
            from pydantic import ValidationError

            message = (
                "Invalid management proposal; no operation was applied"
                if isinstance(exc, ValidationError)
                else str(exc)
            )
            print(f"control-room> {message}")


def main(argv=None):
    raw = list(sys.argv[1:] if argv is None else argv)
    from atbots.platform.management_cli import COMMANDS
    from atbots.platform.management_cli import main as management_main

    command_index = 2 if raw[:1] == ["--root"] and len(raw) > 2 else 0
    if len(raw) > command_index and raw[command_index] in COMMANDS:
        return management_main(raw)
    parser = argparse.ArgumentParser(
        prog="atbots",
        description="Named agents and conversational control room (source feature)",
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT / "platform")
    parser.add_argument("--new", metavar="NAME")
    _options(parser)
    commands = parser.add_subparsers(dest="command")
    agents = commands.add_parser("agents")
    actions = agents.add_subparsers(dest="action", required=True)
    actions.add_parser("list")
    create = actions.add_parser("create")
    create.add_argument("name")
    _options(create)
    show = actions.add_parser("show")
    show.add_argument("name")
    configure = actions.add_parser("configure")
    configure.add_argument("name")
    configure.add_argument("--revision", required=True, type=int)
    configure.add_argument("--state", choices=("active", "paused", "retired"))
    configure.add_argument(
        "--capabilities",
        help="Explicit capability JSON; e.g. approved domains and file grants",
    )
    _options(configure)
    chat = commands.add_parser("chat")
    chat.add_argument("name")
    chat.add_argument("message", nargs="?")
    commands.add_parser("control")
    # Named-agent shorthand, retaining global --root before the name.
    index = 2 if raw[:1] == ["--root"] and len(raw) > 2 else 0
    if (
        len(raw) > index
        and not raw[index].startswith("-")
        and raw[index] not in {"agents", "chat", "control"}
    ):
        raw.insert(index, "chat")
    args = parser.parse_args(raw)
    store = AgentStore(args.root)
    if args.new:
        if args.command:
            parser.error("--new cannot be combined with another command")
        created = store.create(
            args.new,
            binding=_binding(args),
            remote_allowed=bool(args.allow_remote),
            instructions=args.instructions,
        )
        print(
            f"Created {created.name}; model {created.binding.model}; workspace {store.workspace(created.name)}"
        )
        if sys.stdin.isatty():
            _chat(store, created.name)
        return 0
    if args.command in {None, "control"}:
        _control(store)
    elif args.command == "chat":
        _chat(store, args.name, args.message)
    elif args.action == "list":
        _show([a.model_dump(mode="json") for a in store.list()])
    elif args.action == "show":
        _show(store.get(args.name).model_dump(mode="json"))
    elif args.action == "create":
        _show(
            store.create(
                args.name,
                binding=_binding(args),
                remote_allowed=bool(args.allow_remote),
                instructions=args.instructions,
            ).model_dump(mode="json")
        )
    elif args.action == "configure":
        old = store.get(args.name)
        changes = {"binding": _binding(args, old.binding).model_dump()}
        if args.instructions is not None:
            changes["instructions"] = args.instructions
        if args.state is not None:
            changes["state"] = args.state
        if args.capabilities is not None:
            from atbots.platform.models import Capabilities

            changes["capabilities"] = Capabilities.model_validate_json(
                args.capabilities
            ).model_dump()
        if args.allow_remote or args.deny_remote:
            changes["remote_allowed"] = bool(args.allow_remote)
        _show(
            store.configure(
                args.name, expected_revision=args.revision, **changes
            ).model_dump(mode="json")
        )
    return 0
