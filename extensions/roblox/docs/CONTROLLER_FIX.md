# Roblox Studio Controller Fix

## The Problem

Controllers are currently broken in Roblox Studio due to the **Virtual Gamepad Controller Emulator** beta feature. This feature steals the first controller slot (Gamepad1), causing:

- **Character won't move** - Your character remains stationary when using a controller
- **Camera works** - Only the camera responds to controller input
- **Wrong controller slots** - Your physical controller becomes Gamepad2 or Gamepad3 instead of Gamepad1

This is a known issue in Roblox Studio that affects developers testing games with controller support.

## Root Cause

The Virtual Gamepad Controller Emulator feature adds a virtual gamepad that always takes the Gamepad1 slot. Even when disabled through Studio settings, the feature continues to run because the plugin file remains loaded.

The problematic file is:
```
ControlsEmulator.rbxm
```

Located at:
- **Windows:** `%localappdata%/Roblox/Versions/<version>/BuiltInStandalonePlugins/Optimized_Embedded_Signature/`
- **macOS:** `/Applications/RobloxStudio.app/Contents/Resources/BuiltInStandalonePlugins/Optimized_Embedded_Signature/`

## The Solution

The fix is simple: **rename or delete the ControlsEmulator.rbxm file** to prevent it from loading.

### Automated Fix (Recommended)

We provide a Python script that automatically finds and renames the file:

```bash
# Navigate to the roblox extension directory
cd extensions/roblox

# Run the fix script
python3 fix_studio_controllers.py
```

**What it does:**
1. Automatically detects your platform (Windows/macOS)
2. Finds all Roblox Studio installations
3. Locates every ControlsEmulator.rbxm file
4. Renames them to `.disabled_<timestamp>` (preserves original for easy restoration)
5. Shows detailed results

### Script Options

```bash
# Preview what would be changed (safe, makes no modifications)
python3 fix_studio_controllers.py --dry-run

# Apply the fix (renames the files)
python3 fix_studio_controllers.py

# Restore the original behavior (undo the fix)
python3 fix_studio_controllers.py --restore

# Search in a custom directory
python3 fix_studio_controllers.py --path "/custom/path/to/roblox"
```

### Manual Fix

If you prefer to fix it manually:

#### Windows

1. Open File Explorer and navigate to:
   ```
   %localappdata%\Roblox\Versions\
   ```

2. Find the latest version folder (look for `version-<hash>` with the most recent modification date)

3. Navigate to:
   ```
   BuiltInStandalonePlugins\Optimized_Embedded_Signature\
   ```

4. Find `ControlsEmulator.rbxm` and rename it to `ControlsEmulator.rbxm.disabled`

5. Restart Roblox Studio

#### macOS

1. Open Finder and navigate to:
   ```
   /Applications/RobloxStudio.app/Contents/Resources/
   ```

2. Navigate to:
   ```
   BuiltInStandalonePlugins/Optimized_Embedded_Signature/
   ```

3. Find `ControlsEmulator.rbxm` and rename it to `ControlsEmulator.rbxm.disabled`

4. Restart Roblox Studio

**Tip:** You can use Spotlight search (Cmd+Space) to search for "ControlsEmulator.rbxm" to find it quickly.

## Verification

After applying the fix:

1. **Restart Roblox Studio** (important!)
2. **Connect your controller** before opening Studio, or use the built-in gamepad test
3. **Open any game in Studio**
4. **Press Play (F5)** to test in-game
5. **Test character movement** with your controller
   - Character should now move with the left stick
   - Camera should move with the right stick
   - Your controller should be recognized as Gamepad1

### Testing in Studio

You can verify the fix using Studio's gamepad debugger:

1. Open Roblox Studio
2. Go to **Test** tab → **Emulation**
3. Check the **Gamepad** dropdown
4. Your physical controller should appear as **Gamepad1** (not 2 or 3)

## Troubleshooting

### Script Can't Find ControlsEmulator.rbxm

**Possible causes:**
- Roblox Studio is not installed
- Non-standard installation directory
- File already renamed

**Solution:**
```bash
# Use custom path to search your entire Roblox directory
python3 fix_studio_controllers.py --path "/path/to/roblox"
```

### Permission Denied Error

**On macOS:**
```bash
# Run with sudo if needed
sudo python3 fix_studio_controllers.py
```

**On Windows:**
- Right-click Command Prompt → "Run as Administrator"
- Then run the script

### Controllers Still Not Working

1. **Verify the file was renamed:**
   - Check that `ControlsEmulator.rbxm` no longer exists
   - Should see `ControlsEmulator.rbxm.disabled_<timestamp>` instead

2. **Restart Studio completely:**
   - Close all Studio windows
   - Quit from the system tray (if applicable)
   - Reopen Studio

3. **Check controller connection:**
   - Disconnect and reconnect your controller
   - Try a different USB port
   - Check that the controller works in other applications

4. **Multiple Studio versions:**
   - Run the script again to catch any newly installed versions
   - The script searches all version folders

### Need to Restore Original Behavior

If you need the Virtual Gamepad Controller Emulator back:

```bash
python3 fix_studio_controllers.py --restore
```

Or manually rename the file back:
```
ControlsEmulator.rbxm.disabled_<timestamp> → ControlsEmulator.rbxm
```

## How the Script Works

The `fix_studio_controllers.py` script:

1. **Platform Detection:**
   - Detects Windows or macOS
   - Finds the appropriate Roblox installation directory

2. **File Search:**
   - Recursively searches all version folders
   - Finds every `ControlsEmulator.rbxm` file
   - Shows full paths for transparency

3. **Safe Renaming:**
   - Adds `.disabled_<timestamp>` suffix instead of deleting
   - Preserves original file for easy restoration
   - Creates unique names to avoid conflicts

4. **Verification:**
   - Reports success/failure for each file
   - Shows detailed summary
   - Provides next steps

## Technical Details

### Why This Happens

Roblox Studio's Virtual Gamepad Controller Emulator is a beta feature designed to help developers test gamepad controls without a physical controller. However:

1. It creates a virtual Gamepad1 device
2. Physical controllers become Gamepad2, Gamepad3, etc.
3. Most games expect the player's controller to be Gamepad1
4. Disabling the beta feature in Studio settings doesn't unload the plugin
5. The plugin file must be removed/renamed to truly disable it

### Impact on Development

For game developers testing controller support:
- **Character movement scripts** typically listen to Gamepad1
- **Input handling code** may not check multiple gamepad slots
- **Testing becomes impossible** without this fix

### File Safety

Renaming the file is completely safe:
- ✅ **Reversible** - Original file preserved with `.disabled` suffix
- ✅ **No data loss** - No files are deleted
- ✅ **Studio still works** - All other features function normally
- ✅ **No updates broken** - Studio updates won't be affected

### Multi-Version Support

The script handles multiple Studio versions:
- Searches all `version-*` folders
- Finds files in each version's plugin directory
- Renames across all installations
- Useful if you have multiple Studio versions installed

## Future Updates

If Roblox fixes this issue in a future Studio update:
1. The `ControlsEmulator.rbxm` file may be removed or fixed
2. You can restore the original file if needed
3. The script will report if no files are found (already fixed)

## Contributing

Found an issue or improvement? Please report it:
- File an issue at the main Context Foundry repository
- Tag with `extension:roblox` and `controller-fix`
- Include your platform and Studio version

## References

- [Roblox Developer Forum - Controller Issues](https://devforum.roblox.com/)
- [Roblox Studio Beta Features](https://create.roblox.com/docs/studio/setting-up-roblox-studio)
- [Gamepad Input Documentation](https://create.roblox.com/docs/input/gamepad)

---

**Last Updated:** November 2024
**Affects:** Roblox Studio versions with Virtual Gamepad Controller Emulator
**Status:** Workaround available (automated script provided)
