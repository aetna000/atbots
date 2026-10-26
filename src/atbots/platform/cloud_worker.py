"""Single-owner encrypted GCS snapshot runner for Cloud Run Jobs."""

import json
import os
import tempfile
import uuid

from atbots.platform.deployment import pack_state, unpack_state
from atbots.platform.jobs import Operations
from atbots.platform.worker import execute


def main():
    try:
        from google.cloud import storage
    except ImportError:
        raise RuntimeError("Cloud runner requires atbots[cloud]") from None
    uri = os.environ["ATBOTS_STATE_URI"]
    if not uri.startswith("gs://"):
        raise ValueError("State URI must use GCS")
    bucket_name, name = uri[5:].split("/", 1)
    bucket = storage.Client().bucket(bucket_name)
    state, lease = bucket.blob(name), bucket.blob(name + ".lease")
    token = uuid.uuid4().hex
    # Never steal a crashed owner's lease automatically: external effects may
    # be uncertain. Operator must reconcile old execution before removing it.
    lease.upload_from_string(
        json.dumps(
            {"owner": token, "execution": os.environ.get("CLOUD_RUN_EXECUTION")}
        ),
        if_generation_match=0,
    )
    lease.reload()
    lease_generation = lease.generation
    try:
        state.reload()
        generation = state.generation
        payload = state.download_as_bytes(if_generation_match=generation)
        with tempfile.TemporaryDirectory(prefix="atbots-cloud-") as directory:
            key = os.environ["ATBOTS_STATE_KEY"].encode()
            store = unpack_state(payload, directory, key)
            agents = store.list()
            if len(agents) != 1:
                raise ValueError(
                    "Cloud snapshot must contain exactly one authorized agent"
                )
            ops = Operations(store)
            ops.reconcile_stale()
            try:
                from atbots.platform.scheduler import Scheduler

                Scheduler(store).tick()
                for job in ops.list():
                    if job["status"] == "queued":
                        execute(ops, job["id"])
            finally:
                if (
                    json.loads(
                        lease.download_as_text(if_generation_match=lease_generation)
                    )["owner"]
                    != token
                ):
                    raise RuntimeError("Cloud state writer has been fenced")
                state.upload_from_string(
                    pack_state(store, agents[0].name, key),
                    if_generation_match=generation,
                )
    finally:
        lease.delete(if_generation_match=lease_generation)


if __name__ == "__main__":
    main()
