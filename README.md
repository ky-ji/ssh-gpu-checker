# SSH GPU Checker

A lightweight, agentless NVIDIA GPU monitor for SSH aliases. Use the local web
dashboard for continuous status or the original CLI for one-shot inspection and
host recommendations.

## Web dashboard

Install the project and launch the dashboard:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
bin/ssh-gpu-dashboard
```

Open `http://127.0.0.1:8848`. Without `--match`, every explicit alias from the
selected SSH config is displayed. Use one or more patterns to restrict the set:

```bash
bin/ssh-gpu-dashboard --match 'THUSZ*' --match 'lab-gpu-?'
```

Aliases are parsed from `~/.ssh/config`, or from files inside `~/.ssh/configs`
when that directory exists. Optional matching is case-insensitive and uses
shell-style `*` and `?` globs. The dashboard refuses to start if discovery
produces no aliases or explicit patterns match none.

The server binds only to `127.0.0.1` by default and rejects non-loopback bind
addresses. It has no CORS support, remote access, authentication, or TLS because
it is intentionally a local tool.

### Dashboard behavior

- healthy hosts scan independently every 8 seconds by default
- failures retry after 15, 30, then 60 seconds
- scans pause after 30 seconds without snapshot reads from a browser
- reopening the page wakes scanning immediately
- failed hosts keep their last successful GPU rows and label them stale
- manual refresh is non-blocking and coalesces while a host is already scanning
- collection uses system OpenSSH, normal host-key verification, and `nvidia-smi`
- remote machines need no agent, daemon, Python environment, or installed package

Useful dashboard flags:

- `--config-path PATH`: use a specific SSH config file or directory
- `--match GLOB`: optionally filter aliases; repeatable
- `--interval SECONDS`: healthy scan interval, minimum 5, default 8
- `--timeout SECONDS`: SSH connection timeout, default 8
- `--workers N`: maximum simultaneous host scans, default 8
- `--port N`: local web port, default 8848

This MVP keeps only the current in-memory snapshot. It does not store history,
draw time-series charts, send alerts, edit SSH configuration, or run arbitrary
browser-supplied commands.

## One-shot CLI

The existing recommendation command remains available:

```bash
bin/check-ssh-gpu
bin/check-ssh-gpu --match THUSZ --top 3
bin/check-ssh-gpu --match THUSZ --min-free-mb 40000 --max-util 10
bin/check-ssh-gpu --match THUSZ --sort util
bin/check-ssh-gpu --json
```

Its recommendation score combines absolute free GPU memory, free-memory ratio,
and inverse GPU utilization. Hosts are ranked by their best candidate GPU.

Useful CLI flags:

- `--top N`: show the top N recommended hosts
- `--min-free-mb N`: require free memory on the best GPU
- `--max-util N`: exclude hosts above this utilization threshold
- `--sort score|free|util`: select recommendation ordering
- `--json`: emit inspection and recommendation data for automation

## Codex skill installation

```bash
./tools/install_skill.sh
```

This creates a symlink at `~/.codex/skills/check-ssh-gpu`.
