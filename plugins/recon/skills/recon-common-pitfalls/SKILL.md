---
name: recon-common-pitfalls
description: Fleet ops and iDRAC/racadm pitfalls — grep substring matches, SSH hangs, batch output labeling, Dell OME CPLD limitations. Use when scripting fleet checks or batch ops.
metadata:
  cf-stage: both
  cf-keywords: [recon, idrac, racadm, fleet, ssh, ome, dell]
  cf-severity: HIGH
  cf-citations-pass: 0
  cf-citations-wip: 0
---

# Recon Common Pitfalls

Aggregated pitfalls migrated from the legacy `patterns/` JSON store. Each section is one pitfall; the planner should treat them as independent checks.

## grep without -w matches substrings

**ID:** `grep-substring-match` &nbsp;&nbsp; **Severity:** MEDIUM

**Issue.**

grep 'web1' also matches web10, web11, web100 in CSV lookups

**Planner action.**

Always use grep -w for hostname lookups in CSV files

**Reviewer check.**

Check all grep calls against CSV for whole-word matching

## SSH to unreachable iDRAC hangs the entire loop

**ID:** `idrac-ssh-hang` &nbsp;&nbsp; **Severity:** HIGH

**Issue.**

SSH without ConnectTimeout blocks indefinitely when an iDRAC is unreachable, stalling the batch loop

**Planner action.**

Always include -o ConnectTimeout=5 in SSH commands to iDRAC

**Reviewer check.**

Verify all SSH calls in loops have a connect timeout set

## Batch output without host labels is unreadable

**ID:** `unlabeled-batch-output` &nbsp;&nbsp; **Severity:** LOW

**Issue.**

Running commands across hosts without echoing the hostname makes output impossible to correlate

**Planner action.**

Always echo hostname before command output in batch loops

**Reviewer check.**

Check that all batch loops label their output with the current host

## CPLD firmware updates are not supported by Dell OME

**ID:** `cpld-firmware-not-in-ome` &nbsp;&nbsp; **Severity:** HIGH

**Issue.**

Dell OpenManage Enterprise does not support CPLD (Complex Programmable Logic Device) firmware updates. CPLD sits BELOW the iDRAC -- it controls power sequencing, signal routing, and interface logic at the board level. Updating CPLD reboots the iDRAC itself since iDRAC depends on CPLD for its own power sequencing. Symptoms of outdated CPLD include intermittent power issues, unexplained fan behavior, and board-level glitches that don't appear in standard logs. Must use custom tooling or manual DUP methods. High resistance to running the update because: loss of out-of-band access during update, risk of physical truck roll if it fails.

**Planner action.**

When diagnosing unexplained hardware behavior (power, fans, board-level), consider CPLD firmware as a root cause. Use the custom CPLD update tool, not OME.

**Reviewer check.**

Verify CPLD firmware version is checked during hardware troubleshooting. Confirm OME is not being relied on for CPLD updates.
