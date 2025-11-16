# Build Notifications to Discord

Automatic Discord notifications for your Context Foundry builds!

## What You Get

Your Discord channel will automatically receive notifications for:

### 🔨 Build Started
- Sent when autonomous build begins
- Shows project name and task description
- Includes job ID for tracking

### ✅ Build Complete - Success
- Sent when build completes successfully
- Shows duration, phases completed
- Test results (if available)
- Green color with checkmark

### ❌ Build Complete - Failed
- Sent when build fails
- Shows error message
- Duration and job ID
- Red color with X mark

### 🔍 Phase Complete (Optional)
- Tracks individual phases: Scout, Architect, Builder, Test
- Purple color with phase emoji

## Setup

Already done! ✅ Your system is configured and ready.

**What was configured:**
1. Discord webhook added to `.env`
2. Build notification system integrated into daemon runner
3. Automatic notifications on build start/complete

## Testing

Test the notification system:

```bash
# Test build started
python3 tools/build_notifications.py --test start --project "test-app"

# Test build success
python3 tools/build_notifications.py --test success --project "test-app"

# Test build failure
python3 tools/build_notifications.py --test failed --project "test-app"

# Test phase complete
python3 tools/build_notifications.py --test phase --project "test-app"
```

## How It Works

The daemon runner (`context_foundry/daemon/runner.py`) automatically sends notifications:

1. **When build starts** → Sends "Build Started" notification
2. **When build succeeds** → Sends "Build Complete - Success" with metrics
3. **When build fails** → Sends "Build Complete - Failed" with error details

No manual intervention needed - it just works!

## Usage

Run a build as normal, and notifications will be sent automatically:

```bash
# Start daemon
./tools/cfd start

# Submit a build job (notifications will be sent automatically)
./tools/cfd submit "weather-app" "Build a weather app with FastAPI"

# Monitor progress in Discord!
```

## Customizing Notifications

### Disable Notifications

Remove or comment out `DISCORD_WEBHOOK` in `.env`:

```bash
# DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
```

### Multiple Channels

Send different types to different channels:

```bash
# In .env
DISCORD_WEBHOOK_BUILDS=https://discord.com/api/webhooks/channel1/...
DISCORD_WEBHOOK_RELEASES=https://discord.com/api/webhooks/channel2/...
DISCORD_WEBHOOK_ERRORS=https://discord.com/api/webhooks/channel3/...
```

Then modify `build_notifications.py` to use different webhooks based on notification type.

## Manual Notifications

Send custom notifications from your code:

```python
from tools.build_notifications import notify_build_started, notify_build_complete

# Notify build started
notify_build_started(
    project="my-app",
    task="Deploy to production",
    job_id="abc-123"
)

# Notify build complete
notify_build_complete(
    project="my-app",
    status="success",
    duration_seconds=754,  # 12m 34s
    job_id="abc-123",
    tests_passed=142,
    tests_total=142,
    phases_completed=["Scout", "Architect", "Builder", "Test"]
)
```

## Troubleshooting

### Notifications Not Appearing

1. Check `DISCORD_WEBHOOK` is set in `.env`
2. Verify webhook URL is correct
3. Check Discord channel permissions
4. Look for warnings in daemon logs: `./tools/cfd logs <job-id>`

### Rate Limiting

Discord webhooks are rate-limited (30/minute, 5 per 2 seconds). If you're sending many builds in parallel, some notifications may be delayed or dropped.

## Integration with CI/CD

Use build notifications in your deployment pipeline:

```python
# In your deployment script
from tools.build_notifications import BuildNotificationManager

notifier = BuildNotificationManager()

# Start deployment
notifier.notify_build_started(
    project="production",
    task="Deploy v2.0.0"
)

# ... run deployment ...

# Deployment complete
notifier.notify_build_complete(
    project="production",
    status="success",
    duration_seconds=deployment_time
)
```

## Advanced: Custom Notification Types

Create your own custom notifications:

```python
from tools.discord_notify import DiscordNotifier

notifier = DiscordNotifier()

# Custom embed
embed = {
    "title": "🚀 Custom Event",
    "description": "Something awesome happened!",
    "color": 0x00FF00,
    "fields": [
        {"name": "Field 1", "value": "Value 1", "inline": True},
        {"name": "Field 2", "value": "Value 2", "inline": True},
    ]
}

notifier.send_message(embeds=[embed])
```

## Files

- `tools/discord_notify.py` - Core Discord webhook client
- `tools/build_notifications.py` - Build-specific notification manager
- `context_foundry/daemon/runner.py` - Integration with daemon runner
- `docs/DISCORD_INTEGRATION.md` - General Discord webhook documentation

## Support

Questions? Check:
- Discord API docs: https://discord.com/developers/docs
- Test notifications: `python3 tools/build_notifications.py --help`
- Daemon logs: `./tools/cfd logs <job-id>`
