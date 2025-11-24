# Test Roblox Project

Minimal working Roblox project for testing the Context Foundry Roblox extension.

## Purpose

This project validates that:
- Roblox project detection works correctly
- Rojo configuration is valid
- Luau code follows best practices
- Server-authoritative patterns are demonstrated
- Extension integration functions properly

## Structure

```
test_roblox_project/
├── default.project.json         # Rojo project configuration
├── .luaurc                       # Luau strict mode settings
├── README.md                     # This file
└── src/
    ├── ServerScriptService/
    │   └── PlayerManager.lua     # Simple player management
    ├── ReplicatedStorage/
    │   └── TestConfig.lua        # Shared configuration
    └── Workspace/
        ├── Baseplate             # (defined in default.project.json)
        └── SpawnLocation         # (defined in default.project.json)
```

## Building

```bash
# Build to place file
rojo build default.project.json -o dist/Game.rbxlx

# Or serve for live sync
rojo serve default.project.json
```

## Testing Extension Detection

```bash
# From context-foundry root
cd test_roblox_project
python3 -c "
import sys
sys.path.insert(0, '..')
from extensions.roblox.detector import detect_roblox_project
from pathlib import Path
result = detect_roblox_project(Path('.'))
print(result)
"
```

Expected output:
```json
{
  "is_roblox": true,
  "project_type": "roblox-game",
  "project_subtype": "rojo",
  "has_tests": false,
  "complexity": "moderate",
  "confidence": "high",
  "metadata": {
    "rojo_config": "default.project.json"
  }
}
```

## Validation Checklist

- [x] Valid default.project.json
- [x] Luau code with type annotations
- [x] RemoteEvent usage with validation
- [x] Server-authoritative pattern
- [x] Frozen module exports
- [x] Service caching
- [x] .luaurc with strict mode
