---
name: fleet-recon
description: Use when the user is running fleet checks, iDRAC/racadm queries, SSH batch loops, or Dell server inventory lookups from a management server. Covers grep -w hostname lookups, ConnectTimeout SSH options, and labeled batch output.
---

# Recon Extension

**Read this before any infrastructure ops / fleet check work.**

## What Recon Does

Recon provides inventory knowledge, command templates, and learned patterns for quick fleet reconnaissance tasks -- the ad-hoc checks run from a management server against Dell servers via iDRAC, SSH, or SNMP.

## Key Files

| File | Purpose |
|------|---------|
| `config/inventory-schema.json` | CSV column mapping for sourceoftruth.csv |
| `templates/idrac-checks.md` | Proven racadm commands |
| `templates/batch-loops.md` | Loop patterns with proper validation |
| `patterns/recon-common-issues.json` | Learned gotchas |

## Rules

1. **Always read `config/inventory-schema.json` first** to know which CSV columns map to what fields.
2. **Use `grep -w`** (whole-word match) when looking up hostnames in the CSV. Never bare `grep`.
3. **Label output** with `echo "=== $hostname ==="` or similar -- unlabeled output is useless for batch checks.
4. **Quote variables** in loops: `"$i"` not `$i`.
5. **Use host files** (`hosts.rN`) when they exist rather than filtering the full CSV.
6. **SSH to iDRAC**: use `-o StrictHostKeyChecking=no -o ConnectTimeout=5` to avoid hangs on unreachable hosts.
7. **Prefer one-liners** for quick checks. Only generate scripts for multi-step or reusable tasks.
8. **Save useful generated scripts** to `scripts/` with a descriptive filename for reuse.

## Common Patterns

### Basic fleet loop
```bash
for h in $(cat hosts.r10); do
  ip=$(grep -w "$h" ~/sourceoftruth.csv | awk -F, '{print $11}')
  echo "=== $h ($ip) ==="
  # command here
done
```

### iDRAC SSH check
```bash
sshpass -f ~/.idrac_pass ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@"$ip" racadm <command>
```

### Parallel execution (when speed matters)
```bash
cat hosts.r10 | xargs -P 10 -I{} bash -c '
  ip=$(grep -w "{}" ~/sourceoftruth.csv | awk -F, '\''{print $11}'\'')
  echo "=== {} ($ip) ==="
  ssh -o ConnectTimeout=5 root@"$ip" racadm getsysinfo 2>/dev/null | grep -i "bios"
'
```

## After Solving New Issues

When you discover a new gotcha or useful command:
1. Capture it as a skill: `plugins/recon/skills/<slug>/SKILL.md`
2. If it's a reusable command, also add it to the relevant template file
3. If broadly applicable beyond recon, copy to `~/.foundry/skills/<slug>/SKILL.md`
