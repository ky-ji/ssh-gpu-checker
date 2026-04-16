# SSH GPU Checker

One command to inspect NVIDIA GPU availability across SSH aliases from `~/.ssh/config` and recommend the best host for a new workload.

## Usage

```bash
bin/check-ssh-gpu
bin/check-ssh-gpu --match THUSZ --top 3
bin/check-ssh-gpu --match THUSZ --min-free-mb 40000 --max-util 10
bin/check-ssh-gpu --match THUSZ --sort util
bin/check-ssh-gpu --json
```

## Recommendation Model

The default recommendation score combines:

- absolute free GPU memory
- free-memory ratio
- inverse GPU utilization

Recommendations are host-level, but each host is ranked by its best candidate GPU. This makes the top result easier to act on while still showing the underlying GPU evidence.

## Skill Installation

```bash
./tools/install_skill.sh
```

This creates a symlink at `~/.codex/skills/check-ssh-gpu` so Codex can discover the wrapper skill.

## Output

The default text view shows:

- a `Recommended Hosts` section with score and reason
- a `Host Summary` section for all scanned hosts
- per-host GPU rows with total, used, free, and utilization percentages
- failure states such as `unreachable`, `auth_failed`, and `no_nvidia_smi`

## Useful Flags

- `--top N`: show the top N recommended hosts
- `--min-free-mb N`: require at least this much free memory on the best GPU
- `--max-util N`: exclude hosts whose best GPU is busier than this threshold
- `--sort score|free|util`: sort recommendations by combined score, free memory, or utilization
- `--json`: emit raw inspection results plus recommendation data for automation
