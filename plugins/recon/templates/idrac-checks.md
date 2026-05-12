# iDRAC Command Templates

Proven racadm commands for common Dell server checks.

## System Info

```bash
# Full system info (model, service tag, BIOS version, hostname)
racadm getsysinfo

# Just BIOS version
racadm getsysinfo | grep -i "bios version"

# Service tag
racadm getsysinfo | grep -i "service tag"

# System model
racadm getsysinfo | grep -i "system model"
```

## Storage / RAID

```bash
# RAID controller status
racadm raid get status

# List virtual disks
racadm raid get vdisks

# List physical disks
racadm raid get pdisks

# Storage controller info
racadm storage get controllers
```

## Network

```bash
# NIC configuration
racadm get NIC.NICConfig

# Current network settings
racadm getniccfg

# Teaming / bonding status
racadm get NIC.NICConfig.1.Teaming
```

## Firmware

```bash
# Full firmware/software inventory
racadm swinventory

# Lifecycle controller version
racadm getversion

# Check specific component firmware
racadm swinventory | grep -A2 "BIOS"
racadm swinventory | grep -A2 "iDRAC"
racadm swinventory | grep -A2 "NIC"
```

## Power

```bash
# Current power state
racadm serveraction powerstatus

# Power cycle (careful!)
racadm serveraction powercycle

# Graceful shutdown
racadm serveraction graceshutdown
```

## Logs

```bash
# System event log (last 10)
racadm getsel -i 1-10

# Lifecycle log (last 10)
racadm lclog view -i 1-10

# Clear SEL (careful!)
racadm clrsel
```

## Health

```bash
# Overall system health
racadm get System.ServerPwr.PSRollupStatus
racadm get System.ServerTemp.TempRollupStatus

# Fan status
racadm get System.Fan.RedundancyStatus
```
