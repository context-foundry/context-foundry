# Network Check Templates

Commands for network diagnostics and verification.

## DNS Lookups

```bash
# Forward lookup
for h in $(cat hosts.r10); do
  echo -n "$h: "
  dig +short "$h"
done

# Reverse lookup from iDRAC IP
for h in $(cat hosts.r10); do
  ip=$(grep -w "$h" ~/sourceoftruth.csv | awk -F, '{print $11}')
  echo -n "$h ($ip): "
  dig +short -x "$ip"
done
```

## Ping Sweep

```bash
# Quick reachability check
for h in $(cat hosts.r10); do
  ip=$(grep -w "$h" ~/sourceoftruth.csv | awk -F, '{print $11}')
  if ping -c1 -W2 "$ip" &>/dev/null; then
    echo "$h ($ip): UP"
  else
    echo "$h ($ip): DOWN"
  fi
done
```

## Port Check

```bash
# Check if a specific port is open (e.g., 443 for iDRAC web)
for h in $(cat hosts.r10); do
  ip=$(grep -w "$h" ~/sourceoftruth.csv | awk -F, '{print $11}')
  if timeout 2 bash -c "echo >/dev/tcp/$ip/443" 2>/dev/null; then
    echo "$h ($ip): port 443 OPEN"
  else
    echo "$h ($ip): port 443 CLOSED"
  fi
done
```

## SSL Certificate Check

```bash
# Check iDRAC cert expiry
for h in $(cat hosts.r10); do
  ip=$(grep -w "$h" ~/sourceoftruth.csv | awk -F, '{print $11}')
  expiry=$(echo | openssl s_client -connect "$ip":443 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
  echo "$h ($ip): cert expires $expiry"
done
```
