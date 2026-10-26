"""Independent local job process; native Agent owns execution and cancellation."""

import argparse
import threading

from pydantic_ai import CancellationToken

from atbots.platform.jobs import Operations
from atbots.platform.session import AgentSession
from atbots.platform.store import AgentStore


def execute(ops, identity, session_factory=AgentSession):
    job = ops.get(identity)
    token = ops.claim(identity)
    cancellation = CancellationToken()
    stopped = threading.Event()

    def monitor():
        while not stopped.wait(1):
            try:
                if ops.heartbeat(identity, token) == "cancel_requested":
                    cancellation.cancel()
            except RuntimeError:
                cancellation.cancel()
                return

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    try:
        if ops.store.get(job["agent"]).revision != job["definition_revision"]:
            raise RuntimeError("Agent definition changed after job approval")
        result = session_factory(
            ops.store, job["agent"], cancellation_token=cancellation
        ).chat(job["objective"])
        ops.finish(
            identity,
            token,
            "needs_review" if cancellation.cancelled else "replied",
            {
                "answer": result.text,
                "at": result.at,
                "objective_verified": False,
                "requests": result.requests,
                "cost": None,
            },
        )
    except Exception as exc:  # noqa: BLE001 - persist redacted provider/tool failures, never their raw contents
        ops.finish(
            identity,
            token,
            "needs_review" if cancellation.cancelled else "failed",
            {
                "failure_type": type(exc).__name__,
                "objective_verified": False,
                "reason": "Cancelled work may have external effects; inspect before replay"
                if cancellation.cancelled
                else "Inspect provider setup and execution receipts",
            },
        )
    finally:
        stopped.set()
        monitor_thread.join(timeout=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--job", required=True)
    args = parser.parse_args()
    execute(Operations(AgentStore(args.root)), args.job)


if __name__ == "__main__":
    main()
