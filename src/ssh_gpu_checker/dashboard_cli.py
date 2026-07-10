import argparse
import math
from pathlib import Path
from typing import List, Optional, Sequence

import uvicorn

from ssh_gpu_checker.cli import load_hosts, resolve_default_config_path
from ssh_gpu_checker.config import filter_hosts_by_globs
from ssh_gpu_checker.coordinator import ScanCoordinator
from ssh_gpu_checker.inspect import inspect_host
from ssh_gpu_checker.web import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serve the SSH GPU dashboard")
    parser.add_argument("--config-path")
    parser.add_argument(
        "--match",
        action="append",
        help="optional SSH alias glob; repeat for more patterns",
    )
    parser.add_argument("--interval", type=float, default=8.0)
    parser.add_argument("--timeout", type=int, default=8)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8848)
    return parser


def validate_loopback_host(value: str) -> str:
    if value not in {"127.0.0.1", "localhost"}:
        raise ValueError(
            "dashboard host must be loopback-only: use 127.0.0.1 or localhost"
        )
    return value


def select_dashboard_hosts(
    hosts: Sequence[str], patterns: Optional[Sequence[str]]
) -> List[str]:
    if not patterns:
        return list(hosts)
    return filter_hosts_by_globs(hosts, patterns)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not math.isfinite(args.interval) or args.interval < 5:
        parser.error("--interval must be at least 5 seconds")
    if args.timeout < 1:
        parser.error("--timeout must be at least 1 second")
    if args.workers < 1:
        parser.error("--workers must be at least 1")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        host = validate_loopback_host(args.host)
    except ValueError as exc:
        parser.error(str(exc))

    config_path = (
        Path(args.config_path).expanduser()
        if args.config_path
        else resolve_default_config_path()
    )
    try:
        configured_hosts = load_hosts(config_path, None)
    except OSError as exc:
        parser.error(f"could not read SSH config: {exc}")
    selected_hosts = select_dashboard_hosts(configured_hosts, args.match)
    if not selected_hosts:
        parser.error("no SSH aliases were selected")

    coordinator = ScanCoordinator(
        selected_hosts,
        inspect_host,
        interval_seconds=args.interval,
        timeout_seconds=args.timeout,
        workers=args.workers,
    )
    app = create_app(coordinator)
    print(f"SSH GPU Dashboard: http://{host}:{args.port}", flush=True)
    uvicorn.run(app, host=host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
