---
title: SSH GPU Checker Skill Design
date: 2026-04-16
status: draft
---

# SSH GPU Checker Skill Design

## Goal

Create a small Git-managed project at `/Users/jky/workspace/project` that can inspect SSH hosts defined by the user's SSH config and show per-host GPU availability in one command. The project should also expose that capability through a Codex skill so the same workflow can be triggered from natural language.

## Context

- The user's current host aliases are defined in `~/.ssh/config`, not `~/.ssh/configs`.
- The requested workflow is "one click" or "one command" inspection across many SSH aliases.
- The project should be maintainable as a standalone repository and later pushed to GitHub.

## Recommended Approach

Build the core functionality as a local Python CLI and wrap it with a thin Codex skill.

This keeps host discovery, SSH execution, timeout handling, parsing, and output formatting in normal code that is easy to test and extend. The skill remains small and stable because it only needs to invoke the project command and summarize the result for the user.

## Alternatives Considered

### Shell-only script

Fastest to write, but weaker error handling, harder to test, and more painful to extend with filtering, sorting, structured output, or cross-platform behavior.

### Skill-only workflow

A skill alone cannot be the durable implementation because the logic would live in prompt instructions instead of versioned code. That makes maintenance and GitHub publication much worse.

## Repository Shape

The repository root will be `/Users/jky/workspace/project`.

Planned structure:

- `README.md`: setup, usage, and publishing notes
- `bin/check-ssh-gpu`: stable one-command entrypoint
- `src/ssh_gpu_checker/`: host discovery, SSH execution, GPU parsing, table rendering
- `tests/`: unit tests for parsing and host selection
- `skills/check-ssh-gpu/SKILL.md`: Codex skill wrapper
- `tools/install_skill.sh`: helper to install or symlink the skill into the local Codex skills directory
- `docs/superpowers/specs/`: design and planning docs

## Core Behavior

### Host discovery

- Read host aliases from `~/.ssh/config` by default
- Support overriding the SSH config path with a CLI flag
- Ignore wildcard and pattern-based `Host` entries such as `*`
- Allow optional name filtering, for example matching only `THUSZ`

### GPU inspection

For each selected alias, execute:

```bash
ssh <alias> "nvidia-smi --query-gpu=index,name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits"
```

The tool will compute:

- GPU index
- GPU model name
- total memory
- used memory
- free memory
- GPU utilization

### Output

Default output will be a readable terminal table grouped by host, plus a compact host-level summary sorted by the best available free memory so the user can quickly choose a machine.

Each host should end in one of these states:

- `ok`: GPU data collected successfully
- `unreachable`: SSH timeout, DNS, routing, or refused connection
- `auth_failed`: SSH authentication failure
- `no_nvidia_smi`: command not found on remote host
- `no_gpu_data`: command ran but returned no GPU rows
- `error`: any unexpected failure

### Skill wrapper

The skill will:

- trigger when the user asks to inspect SSH host GPU availability
- call the repository entrypoint rather than reimplementing the logic
- summarize which hosts appear most available
- mention failures briefly without hiding them

## User Experience

The primary direct command should look like:

```bash
bin/check-ssh-gpu
```

Likely useful follow-up flags:

- `--config-path <path>`
- `--match <substring>`
- `--timeout <seconds>`
- `--workers <n>`
- `--json`

## Error Handling

- Each host must have an individual timeout so one slow machine does not block the whole run
- Failures on one host must not abort the batch
- Exit status should be non-zero only for tool-level failure, not because one or more hosts were unreachable

## Testing

Initial automated coverage should focus on:

- SSH config host extraction
- free-memory computation from `nvidia-smi` rows
- host status mapping from stderr and exit codes
- sorting and summary rendering

Remote integration tests will be manual because they depend on live hosts and credentials.

## Non-Goals

- automatic job scheduling on remote machines
- continuous monitoring daemon behavior
- support for non-NVIDIA GPU tooling in the first version

## Open Questions Resolved

- The repository should live directly at `/Users/jky/workspace/project`.
- The skill is a wrapper over code in the repository, not the primary implementation.
- GitHub publication is part of the maintenance path, but the remote repository target can be decided after local implementation is complete.
