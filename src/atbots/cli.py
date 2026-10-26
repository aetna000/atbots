"""Development CLI for the AtMem intelligence companion."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from atbots.companion import CompanionRuntime
from atbots.config import DEFAULT_CONFIG, AtBotConfig, ProviderConfig, load_config, save_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atbots", description="AtBots local-first agents",
        epilog="Source platform: atbots (control room), atbots --new NAME, atbots NAME, atbots agents --help. Legacy companion commands remain available."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    commands = parser.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth", help="Sign in to native account providers; no model calls")
    actions = auth.add_subparsers(dest="auth_action", required=True)
    for action in ("login", "status", "logout"):
        item = actions.add_parser(action)
        item.add_argument("provider", choices=("chatgpt", "github-copilot", "anthropic"))
        item.add_argument("--profile", default="default")
        if action == "login":
            item.add_argument("--client-id", help="Your own device-enabled GitHub OAuth application client ID")
            item.add_argument("--timeout", type=int, default=300)
    init = commands.add_parser("init", help="Configure the local AtMem companion")
    init.add_argument("--model", default="qwen3:4b")
    init.add_argument("--endpoint", default="http://127.0.0.1:11434")
    init.add_argument(
        "--num-ctx",
        type=int,
        default=8192,
        help="Context window for the local model (0 leaves the server default).",
    )
    init.add_argument("--force", action="store_true")
    commands.add_parser("status", help="Show companion capabilities and providers")
    commands.add_parser("doctor", help="Check companion readiness")
    serve = commands.add_parser("serve", help="Run the private headless companion")
    serve.add_argument("--host")
    serve.add_argument("--port", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    legacy = {"auth", "init", "status", "doctor", "serve"}
    if not raw or raw[0] in {"--root", "--new", "agents", "chat", "control"} or (
        not raw[0].startswith("-") and raw[0] not in legacy
    ):
        from atbots.platform.cli import main as platform_main
        try:
            return platform_main(raw)
        except (ValueError, RuntimeError, OSError) as exc:
            # Pydantic validation may echo user-supplied secret values.
            from pydantic import ValidationError
            message = "Invalid agent configuration; inspect field names and policy (credential values are not accepted)" if isinstance(exc, ValidationError) else str(exc)
            print(f"error: {message}", file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            print("Conversation cancelled; no task replay requested.", file=sys.stderr)
            return 130
    args = _parser().parse_args(argv)
    try:
        if args.command == "auth":
            from atbots.auth import auth_status, login, logout
            if args.auth_action == "login":
                value = asyncio.run(login(args.provider, args.profile, client_id=args.client_id,
                                          timeout=args.timeout))
            elif args.auth_action == "logout":
                value = logout(args.provider, args.profile)
            else:
                value = auth_status(args.provider, args.profile)
            print(json.dumps(value, indent=2, sort_keys=True))
            if args.auth_action == "logout":
                return 0
            return 0 if value.get("state") == "saved" else 1
        if args.command == "init":
            target = Path(args.config).expanduser()
            if target.exists() and not args.force:
                raise ValueError(f"configuration already exists: {target} (use --force)")
            config = AtBotConfig(
                profile="memory-companion",
                providers=[
                    ProviderConfig(
                        model=args.model,
                        endpoint=args.endpoint,
                        num_ctx=args.num_ctx or None,
                    )
                ],
            )
            save_config(config, target)
            print(f"AtBot companion configured: {target}")
            print(f"Local model: {args.model} via Ollama")
            if args.num_ctx:
                print(
                    f"Context window: {args.num_ctx} "
                    "(AtBots derives a model tag on first use; Ollama's "
                    "OpenAI-compatible endpoint ignores per-request num_ctx)"
                )
            print("AtMem owns storage and the customer dashboard.")
            return 0
        config = load_config(args.config)
        companion = CompanionRuntime(config)
        if args.command in {"status", "doctor"}:
            value = companion.capabilities()
            value["config_path"] = str(Path(args.config).expanduser())
            print(json.dumps(value, indent=2, sort_keys=True))
            ready = any(bool(row.get("available")) for row in value["providers"])
            return 0 if ready else 1
        if args.command == "serve":
            from atbots.service import serve

            serve(config, host=args.host or config.host, port=args.port or config.port)
            return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Sign-in cancelled.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
