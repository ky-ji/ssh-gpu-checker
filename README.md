# SSH GPU Checker

A lightweight real-time dashboard for NVIDIA GPUs on your SSH servers.

## Quick start

Run:

```bash
uvx --from git+https://github.com/ky-ji/ssh-gpu-checker.git ssh-gpu-dashboard
```

Then open [http://127.0.0.1:8848](http://127.0.0.1:8848).

The dashboard automatically reads `~/.ssh/config`, displays all explicit SSH
aliases, and refreshes their GPU status. Nothing needs to be installed on the
remote servers. Press `Ctrl+C` to stop.

> Don't have `uv`? [Install it here](https://docs.astral.sh/uv/getting-started/installation/).

## Show only some servers (optional)

Use `--match` only when you do not want to display every server:

```bash
uvx --from git+https://github.com/ky-ji/ssh-gpu-checker.git ssh-gpu-dashboard --match 'lab-gpu-*'
```

Without `--match`, all servers are shown. The pattern supports `*` and `?`, and
you can repeat `--match`.

## Use the short command (optional)

If you use the dashboard often, install the short command once:

```bash
uv tool install git+https://github.com/ky-ji/ssh-gpu-checker.git
```

After that, start it from any directory with:

```bash
ssh-gpu-dashboard
```

Update it later with `uv tool upgrade ssh-gpu-checker`.

## Requirements

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and OpenSSH on your computer
- SSH aliases in `~/.ssh/config`
- NVIDIA drivers and `nvidia-smi` on the remote servers

## One-shot check (optional)

For a terminal-only snapshot and host recommendation:

```bash
uvx --from git+https://github.com/ky-ji/ssh-gpu-checker.git ssh-gpu-checker
```

Run `ssh-gpu-dashboard --help` or `ssh-gpu-checker --help` after permanent
installation for all options. The dashboard is local-only and does not modify
your SSH configuration.
