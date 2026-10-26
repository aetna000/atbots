"""Installed-wheel qualification on an existing Windows SSH host and its WSL.

Requires an operator-authenticated SSH control socket. Never stores passwords,
copies env files, updates existing environments, or provisions cloud resources.
"""

import argparse
import base64
import json
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--linux", action="store_true")
    parser.add_argument(
        "--linux-install-deps",
        action="store_true",
        help="Install Playwright's OS browser libraries in the existing WSL distro",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    evidence = Path(tempfile.mkdtemp(prefix="atbots-remote-evidence-"))
    identity = "atbots-nondeploy-" + uuid.uuid4().hex[:12]
    relative = "AppData/Local/Temp/" + identity
    ssh = ["ssh", "-S", args.socket, args.host]

    def powershell(script, timeout=1800):
        encoded = base64.b64encode(
            ("$ErrorActionPreference='Stop'; " + script).encode("utf-16-le")
        ).decode()
        return subprocess.run(
            [*ssh, "powershell", "-NoProfile", "-EncodedCommand", encoded],
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    result = powershell(
        "$p=Join-Path $env:TEMP '"
        + identity
        + "'; if((Get-PSDrive C).Free -lt 3GB){throw 'Need 3 GB free for isolated acceptance'}; New-Item -ItemType Directory -Path $p | Out-Null; Write-Output $p",
        timeout=30,
    )
    if result.returncode:
        raise RuntimeError("Remote directory/disk pilot failed")
    remote = result.stdout.decode(errors="replace").strip()
    archive = evidence / "suite.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(root / "pyproject.toml", "pyproject.toml")
        for path in (root / "tests").glob("*.py"):
            bundle.write(path, "tests/" + path.name)
        for path in (root / "evals").glob("*.py"):
            bundle.write(path, "evals/" + path.name)
        bundle.write(
            root / "evals/platform-intents-v1.json", "evals/platform-intents-v1.json"
        )
        bundle.write(args.wheel, args.wheel.name)
    subprocess.run(
        [
            "scp",
            "-o",
            "ControlPath=" + args.socket,
            str(archive),
            args.host + ":" + relative + "/suite.zip",
        ],
        check=True,
        timeout=60,
    )
    install = "[dev,auth,anthropic,browser,schedule,supervision]"
    script = f"$p=Join-Path $env:TEMP '{identity}'; Expand-Archive -LiteralPath ($p+'/suite.zip') -DestinationPath ($p+'/suite'); python -m venv ($p+'/venv'); if($LASTEXITCODE){{exit $LASTEXITCODE}}; $py=$p+'/venv/Scripts/python.exe'; & $py -m pip install ($p+'/suite/{args.wheel.name}{install}'); if($LASTEXITCODE){{exit $LASTEXITCODE}}; & $py -m playwright install chromium; if($LASTEXITCODE){{exit $LASTEXITCODE}}; Set-Location ($p+'/suite'); & $py -m pytest -q; exit $LASTEXITCODE"
    print(
        json.dumps(
            {
                "evidence": str(evidence),
                "windows_root": remote,
                "phase": "install/test isolated Windows wheel",
            }
        ),
        flush=True,
    )
    result = powershell(script)
    (evidence / "windows.log").write_bytes(result.stdout + result.stderr)
    summary = {
        "windows": {"exit_code": result.returncode, "root": remote},
        "evidence": str(evidence),
        "cloud_resources_created": False,
    }
    print(json.dumps({"windows_exit_code": result.returncode}), flush=True)
    if args.linux:
        # The archive is already on the same physical machine, exposed by WSL's
        # standard drive mount. Only a new /tmp environment is created in Ubuntu.
        # WSL may stop between SSH invocations and clear /tmp. Keep this
        # isolated, uniquely named test environment across those restarts.
        linux_root = "/var/tmp/" + identity
        mounted = "/mnt/" + remote[0].lower() + remote[2:].replace("\\", "/") + "/suite"
        bootstrap = "import venv; venv.create('" + linux_root + "/venv',with_pip=True)"
        encoded = base64.b64encode(bootstrap.encode()).decode()
        os_dependencies = (
            f"& wsl.exe -d Ubuntu -u root --exec {linux_root}/venv/bin/python -m playwright install-deps chromium; if($LASTEXITCODE){{exit $LASTEXITCODE}}; "
            if args.linux_install_deps
            else ""
        )
        linux_command = f"& wsl.exe -d Ubuntu --exec python3 -c \"import base64;exec(base64.b64decode('{encoded}'))\"; if($LASTEXITCODE){{exit $LASTEXITCODE}}; & wsl.exe -d Ubuntu --exec {linux_root}/venv/bin/python -m pip install '{mounted}/{args.wheel.name}{install}'; if($LASTEXITCODE){{exit $LASTEXITCODE}}; {os_dependencies}& wsl.exe -d Ubuntu --exec {linux_root}/venv/bin/python -m playwright install chromium; if($LASTEXITCODE){{exit $LASTEXITCODE}}; & wsl.exe -d Ubuntu --cd '{mounted}' --exec {linux_root}/venv/bin/python -m pytest -q; exit $LASTEXITCODE"
        print(
            json.dumps(
                {"phase": "install/test isolated WSL Ubuntu wheel", "root": linux_root}
            ),
            flush=True,
        )
        result = powershell(linux_command)
        (evidence / "linux.log").write_bytes(result.stdout + result.stderr)
        summary["linux"] = {"exit_code": result.returncode, "root": linux_root}
    (evidence / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
