# Batch Loop Templates

Patterns for running commands across multiple hosts.

## Basic Sequential Loop

The workhorse. One host at a time, labeled output.

```bash
for h in $(cat hosts.r10); do
  ip=$(grep -w "$h" ~/sourceoftruth.csv | awk -F, '{print $11}')
  echo "=== $h ($ip) ==="
  # your command here using $ip
done
```

## iDRAC SSH Loop

Sequential loop with SSH to iDRAC. Includes timeout and host key bypass.

```bash
for h in $(cat hosts.r10); do
  ip=$(grep -w "$h" ~/sourceoftruth.csv | awk -F, '{print $11}')
  echo "=== $h ($ip) ==="
  sshpass -f ~/.idrac_pass ssh \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout=5 \
    root@"$ip" racadm getsysinfo 2>/dev/null | grep -i "bios version"
done
```

## Parallel Loop (xargs)

Run across many hosts in parallel. `-P 10` = 10 concurrent.

```bash
cat hosts.r10 | xargs -P 10 -I{} bash -c '
  ip=$(grep -w "{}" ~/sourceoftruth.csv | awk -F, '\''{ print $11 }'\'')
  result=$(sshpass -f ~/.idrac_pass ssh \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout=5 \
    root@"$ip" racadm getsysinfo 2>/dev/null | grep -i "bios version")
  echo "=== {} ($ip) === $result"
'
```

## CSV Lookup Only (No SSH)

Just pull a field from the CSV for each host. No remote access needed.

```bash
for h in $(cat hosts.r10); do
  echo -n "$h: "
  grep -w "$h" ~/sourceoftruth.csv | awk -F, '{print $11}'
done
```

## Multi-Column Lookup

Pull multiple fields at once.

```bash
for h in $(cat hosts.r10); do
  grep -w "$h" ~/sourceoftruth.csv | awk -F, '{printf "%-20s %-15s %-15s %s\n", $1, $3, $11, $5}'
done
```

## Loop with Error Handling

Skip unreachable hosts and log failures.

```bash
failed=""
for h in $(cat hosts.r10); do
  ip=$(grep -w "$h" ~/sourceoftruth.csv | awk -F, '{print $11}')
  echo "=== $h ($ip) ==="
  if ! sshpass -f ~/.idrac_pass ssh \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout=5 \
    root@"$ip" racadm getsysinfo 2>/dev/null | grep -i "bios version"; then
    echo "  FAILED - unreachable"
    failed="$failed $h"
  fi
done
[ -n "$failed" ] && echo -e "\nFailed hosts:$failed"
```

## Output to File

Same loop, but capture structured output.

```bash
outfile="recon-$(date +%Y%m%d-%H%M).csv"
echo "hostname,idrac_ip,bios_version" > "$outfile"
for h in $(cat hosts.r10); do
  ip=$(grep -w "$h" ~/sourceoftruth.csv | awk -F, '{print $11}')
  bios=$(sshpass -f ~/.idrac_pass ssh \
    -o StrictHostKeyChecking=no \
    -o ConnectTimeout=5 \
    root@"$ip" racadm getsysinfo 2>/dev/null | grep -i "bios version" | awk '{print $NF}')
  echo "$h,$ip,$bios" >> "$outfile"
done
echo "Saved to $outfile"
```
