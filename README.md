# SSH GPU Checker

One command to inspect NVIDIA GPU availability across SSH aliases from `~/.ssh/config`.

## Usage

```bash
bin/check-ssh-gpu
bin/check-ssh-gpu --match THUSZ
bin/check-ssh-gpu --config-path ~/.ssh/config --timeout 5 --workers 4
bin/check-ssh-gpu --json
```

## Skill Installation

```bash
./tools/install_skill.sh
```

This creates a symlink at `~/.codex/skills/check-ssh-gpu` so Codex can discover the wrapper skill.

## Output

The default text view shows:

- a host summary sorted by the best free GPU memory
- per-host GPU rows with total, used, free, and utilization percentages
- failure states such as `unreachable`, `auth_failed`, and `no_nvidia_smi`
