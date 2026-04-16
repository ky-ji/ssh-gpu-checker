---
name: check-ssh-gpu
description: Use when inspecting GPU memory availability or idle NVIDIA GPUs across SSH aliases defined in the local SSH config
---

# Check SSH GPU

Run the repository tool instead of reimplementing SSH calls or GPU parsing inside the prompt.

## Quick Reference

- Repository root: `/Users/jky/workspace/project`
- All hosts: `bin/check-ssh-gpu`
- Filter hosts: `bin/check-ssh-gpu --match THUSZ`
- JSON output: `bin/check-ssh-gpu --json`
- Alternate config: `bin/check-ssh-gpu --config-path ~/.ssh/config`

## Notes

- The command reads SSH aliases from `~/.ssh/config` by default.
- Failures are reported per host so one broken machine does not stop the full scan.
- Prefer the text view for quick picking and `--json` for automation.
