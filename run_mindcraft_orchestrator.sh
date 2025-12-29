#!/bin/bash
# Run Mindcraft Orchestrator
# Usage: ./run_mindcraft_orchestrator.sh [--dry-run]

cd /home/chuck/homelab/context-foundry
source venv/bin/activate

DRY_RUN=""
if [ "$1" == "--dry-run" ]; then
    DRY_RUN="True"
else
    DRY_RUN="False"
fi

python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')
from extensions.mindcraft.orchestrator import MindcraftOrchestrator

async def run():
    print('🚀 Starting Mindcraft Orchestrator')
    print('   Dry Run: $DRY_RUN')
    print('   Server: ws://localhost:8080')
    print('   Press Ctrl+C to stop')
    print('')

    orch = MindcraftOrchestrator(dry_run=$DRY_RUN)
    await orch.start()

asyncio.run(run())
"
