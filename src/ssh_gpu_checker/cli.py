import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Sequence

from ssh_gpu_checker.config import parse_ssh_hosts
from ssh_gpu_checker.inspect import inspect_many_hosts
from ssh_gpu_checker.render import render_report


def resolve_default_config_path() -> Path:
    configs_dir = Path('~/.ssh/configs').expanduser()
    if configs_dir.is_dir():
        return configs_dir
    return Path('~/.ssh/config').expanduser()


def load_hosts(config_path: Path, match: Optional[str]) -> List[str]:
    if config_path.is_dir():
        texts = [path.read_text(encoding='utf-8') for path in sorted(config_path.iterdir()) if path.is_file()]
        hosts = []
        for text in texts:
            hosts.extend(parse_ssh_hosts(text))
    else:
        hosts = parse_ssh_hosts(config_path.read_text(encoding='utf-8'))
    if match:
        lowered = match.lower()
        hosts = [host for host in hosts if lowered in host.lower()]
    return hosts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Inspect GPU availability across SSH hosts')
    parser.add_argument('--config-path', default=None)
    parser.add_argument('--match')
    parser.add_argument('--timeout', type=int, default=8)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--json', action='store_true', dest='as_json')
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_path = Path(args.config_path).expanduser() if args.config_path else resolve_default_config_path()
    hosts = load_hosts(config_path, args.match)
    results = inspect_many_hosts(hosts, timeout=args.timeout, workers=args.workers)
    if args.as_json:
        print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    else:
        print(render_report(results))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
