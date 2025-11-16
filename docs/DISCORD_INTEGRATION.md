# Discord Integration Guide

Send automated notifications to Discord channels for releases, builds, and custom communications.

## Quick Start

### 1. Create a Discord Webhook

1. Go to your Discord server
2. Right-click the channel where you want notifications
3. Select **Edit Channel** → **Integrations** → **Webhooks**
4. Click **New Webhook**
5. Copy the **Webhook URL**

### 2. Configure Environment

Add to your `.env` file:

```bash
DISCORD_WEBHOOK=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

### 3. Send Your First Message

**Command Line:**
```bash
python tools/discord_notify.py "Hello from Context Foundry!"
```

**Python Code:**
```python
from tools.discord_notify import DiscordNotifier

notifier = DiscordNotifier()
notifier.send_simple("🤖 Build started!")
```

## Common Use Cases

### Release Announcements

```python
from tools.discord_notify import DiscordNotifier

notifier = DiscordNotifier()
notifier.send_release(
    version="v1.2.3",
    title="New Feature Release",
    description="Added Discord integration and improved performance",
    url="https://github.com/your-repo/releases/v1.2.3"
)
```

**Command Line:**
```bash
python tools/discord_notify.py \
    --release "v1.2.3" \
    --title "New Feature Release" \
    --url "https://github.com/your-repo/releases/v1.2.3" \
    "Added Discord integration and improved performance"
```

### Build Notifications

```python
notifier.send_build_complete(
    project="my-app",
    status="success",
    duration="12m 34s",
    tests_passed=142,
    tests_total=142
)
```

### Custom Rich Messages

```python
embed = {
    "title": "🎯 Deployment Complete",
    "description": "Production deployment successful",
    "color": 0x00FF00,  # Green
    "fields": [
        {"name": "Environment", "value": "Production", "inline": True},
        {"name": "Services", "value": "5 updated", "inline": True},
    ],
    "timestamp": notifier._get_timestamp()
}

notifier.send_message(content=None, embeds=[embed])
```

### Error/Warning Notifications

```python
embed = {
    "title": "⚠️ Build Warning",
    "description": "Build completed with warnings",
    "color": 0xFFA500,  # Orange
    "fields": [
        {"name": "Warnings", "value": "3", "inline": True},
        {"name": "Details", "value": "See logs for more info", "inline": False}
    ]
}

notifier.send_message(embeds=[embed])
```

## Integration Examples

### Notify on Successful Build

Add to your build script:

```python
from tools.discord_notify import DiscordNotifier

def on_build_complete(project, duration, tests):
    try:
        notifier = DiscordNotifier()
        notifier.send_build_complete(
            project=project,
            status="success",
            duration=duration,
            tests_passed=tests['passed'],
            tests_total=tests['total']
        )
    except Exception as e:
        print(f"Discord notification failed: {e}")
```

### Automated Release Notifications

Add to your CI/CD pipeline:

```bash
# In your GitHub Actions or deployment script
python tools/discord_notify.py \
    --release "$VERSION" \
    --title "Production Release" \
    --url "$GITHUB_URL/releases/$VERSION" \
    "Deployed to production. All systems operational."
```

### Scheduled Status Updates

```python
# In a cron job or scheduled task
from tools.discord_notify import DiscordNotifier
import subprocess

def send_daily_status():
    notifier = DiscordNotifier()

    # Get system status
    result = subprocess.run(['df', '-h'], capture_output=True, text=True)
    disk_usage = result.stdout

    embed = {
        "title": "📊 Daily System Status",
        "color": 0x5865F2,
        "fields": [
            {"name": "Status", "value": "✅ All systems operational"},
            {"name": "Uptime", "value": "7 days, 3 hours"}
        ]
    }

    notifier.send_message(embeds=[embed])
```

## Embed Color Reference

```python
SUCCESS = 0x00FF00   # Green
ERROR = 0xFF0000     # Red
WARNING = 0xFFA500   # Orange
INFO = 0x5865F2      # Discord Blurple
NEUTRAL = 0x95A5A6   # Gray
```

## Webhook URL Security

**⚠️ Important:** Never commit webhook URLs to version control!

- ✅ Store in `.env` file (already in `.gitignore`)
- ✅ Use environment variables in CI/CD
- ❌ Never hardcode in source files
- ❌ Never commit `.env` file

## Multiple Webhooks

Send to different channels for different types of notifications:

```bash
# In .env
DISCORD_WEBHOOK_RELEASES=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_BUILDS=https://discord.com/api/webhooks/...
DISCORD_WEBHOOK_ERRORS=https://discord.com/api/webhooks/...
```

```python
release_notifier = DiscordNotifier(os.getenv("DISCORD_WEBHOOK_RELEASES"))
build_notifier = DiscordNotifier(os.getenv("DISCORD_WEBHOOK_BUILDS"))
error_notifier = DiscordNotifier(os.getenv("DISCORD_WEBHOOK_ERRORS"))
```

## Troubleshooting

### Message Not Appearing

1. Check webhook URL is correct
2. Verify channel permissions
3. Check Discord server settings allow webhooks
4. Look for error messages in console

### Rate Limits

Discord webhooks are rate-limited:
- 30 requests per minute per webhook
- 5 requests per 2 seconds per webhook

If sending many messages, add delays:

```python
import time

for message in messages:
    notifier.send_simple(message)
    time.sleep(0.5)  # 500ms delay
```

## Examples

See `tools/discord_examples.py` for complete working examples:

```bash
python tools/discord_examples.py
```

## Advanced: Discord Bot (Full API)

For two-way communication and advanced features, consider creating a Discord bot:

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Add a bot user
4. Invite bot to your server
5. Use discord.py library for full API access

**Note:** Webhooks are sufficient for most notification use cases.

## Resources

- [Discord Webhook Documentation](https://discord.com/developers/docs/resources/webhook)
- [Discord Embed Reference](https://discord.com/developers/docs/resources/channel#embed-object)
- [Discord Developer Portal](https://discord.com/developers/applications)

## Support

Questions or issues? Check `tools/discord_examples.py` for working examples or review the Discord API documentation.
