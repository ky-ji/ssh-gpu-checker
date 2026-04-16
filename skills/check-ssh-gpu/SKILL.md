---
name: check-ssh-gpu
description: Use when choosing the best SSH host for a new GPU workload, comparing multiple SSH aliases, or summarizing which machine is most available
---

# Check SSH GPU

Use the repository tool to recommend the best host instead of manually ranking raw GPU metrics in the prompt.

## Overview

This skill is for “where should I run this next job?” decisions.

Prefer host recommendations over raw dumps. The tool already combines free memory and GPU utilization, so the model should use that ranking first and then explain the top result in plain language.

## Quick Reference

- Repository root: `/Users/jky/workspace/project/ssh-gpu-checker`
- Broad recommendation: `bin/check-ssh-gpu --top 3`
- Narrow to a host group: `bin/check-ssh-gpu --match THUSZ --top 3`
- Require larger free memory: `bin/check-ssh-gpu --match THUSZ --min-free-mb 40000 --top 3`
- Prefer quieter machines: `bin/check-ssh-gpu --match THUSZ --max-util 10 --sort util --top 3`
- Automation-friendly output: `bin/check-ssh-gpu --match THUSZ --json`

## Workflow

1. Start with a filtered recommendation command if the user already knows the cluster or host prefix.
2. Read the `Recommended Hosts` section first.
3. Report the top host with its reason before mentioning backups.
4. Mention failed hosts briefly, but do not let them dominate the answer.
5. Use `--json` only when the output will be consumed by another tool or when the user explicitly wants structured data.

## Response Pattern

For human-facing answers, summarize like this:

- best host
- why it won
- one or two fallback hosts if useful
- any notable failures such as `auth_failed` or `unreachable`

## Common Mistakes

- Do not rank hosts by free memory alone when the tool already provides a combined recommendation score.
- Do not dump every GPU row unless the user asked for raw details.
- Do not hide failed hosts completely; mention them briefly so the user knows the scan was partial.
- Do not use `--json` for normal conversational answers unless structured output is needed.
