#!/usr/bin/env python3
"""
Enhanced Flask-based Web Dashboard for Evolution System
Real-time monitoring with GitHub PR integration and human-in-the-loop workflow
"""

from flask import Flask, render_template_string, jsonify
import sqlite3
from pathlib import Path
from datetime import datetime
import subprocess
import json
import os
import requests
from typing import List, Dict, Optional

app = Flask(__name__)

# GitHub configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')  # Optional: set for higher rate limits
GITHUB_REPO = os.environ.get('GITHUB_REPO', 'context-foundry')  # Default repo name
GITHUB_OWNER = None  # Will be auto-detected from git remote

def get_github_owner() -> Optional[str]:
    """Auto-detect GitHub owner from git remote"""
    global GITHUB_OWNER
    if GITHUB_OWNER:
        return GITHUB_OWNER

    try:
        # Get git remote URL
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=Path(__file__).parent.parent.parent.parent
        )

        if result.returncode != 0:
            return None

        url = result.stdout.strip()

        # Parse owner from URL (supports both HTTPS and SSH)
        # https://github.com/owner/repo.git
        # git@github.com:owner/repo.git
        if 'github.com' in url:
            if url.startswith('https://'):
                parts = url.replace('https://github.com/', '').split('/')
            elif url.startswith('git@'):
                parts = url.replace('git@github.com:', '').split('/')
            else:
                return None

            if len(parts) >= 2:
                GITHUB_OWNER = parts[0]
                return GITHUB_OWNER

        return None
    except Exception as e:
        print(f"Error detecting GitHub owner: {e}")
        return None

def get_open_prs() -> List[Dict]:
    """Fetch open PRs from GitHub API"""
    owner = get_github_owner()
    if not owner:
        return []

    try:
        headers = {}
        if GITHUB_TOKEN:
            headers['Authorization'] = f'token {GITHUB_TOKEN}'

        # GitHub API: List pull requests
        url = f'https://api.github.com/repos/{owner}/{GITHUB_REPO}/pulls'
        params = {'state': 'open', 'sort': 'created', 'direction': 'desc'}

        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code != 200:
            print(f"GitHub API error: {response.status_code}")
            return []

        prs = response.json()

        # Filter for Evolution System PRs (created by self-improvement)
        evolution_prs = []
        for pr in prs:
            # Check if PR is from self-improvement branch
            if 'self-improvement' in pr.get('head', {}).get('ref', ''):
                evolution_prs.append({
                    'number': pr['number'],
                    'title': pr['title'],
                    'url': pr['html_url'],
                    'branch': pr['head']['ref'],
                    'created_at': pr['created_at'],
                    'user': pr['user']['login'],
                    'labels': [label['name'] for label in pr.get('labels', [])]
                })

        return evolution_prs
    except Exception as e:
        print(f"Error fetching PRs: {e}")
        return []

def check_pr_merged(pr_number: int) -> bool:
    """Check if a specific PR has been merged"""
    owner = get_github_owner()
    if not owner:
        return False

    try:
        headers = {}
        if GITHUB_TOKEN:
            headers['Authorization'] = f'token {GITHUB_TOKEN}'

        url = f'https://api.github.com/repos/{owner}/{GITHUB_REPO}/pulls/{pr_number}'
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code != 200:
            return False

        pr_data = response.json()
        return pr_data.get('merged', False)
    except Exception as e:
        print(f"Error checking PR status: {e}")
        return False

# HTML Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Context Foundry Evolution System</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }

        /* PR Notification Banner */
        .pr-banner {
            background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 25px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            animation: pulseGlow 2s infinite;
        }
        .pr-banner h2 {
            font-size: 1.8em;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .pr-banner-icon {
            font-size: 2em;
            animation: bounce 1s infinite;
        }
        .pr-banner-button {
            display: inline-block;
            background: white;
            color: #ef4444;
            padding: 12px 24px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            margin-top: 12px;
            transition: transform 0.2s;
        }
        .pr-banner-button:hover {
            transform: scale(1.05);
        }
        @keyframes pulseGlow {
            0%, 100% { box-shadow: 0 10px 40px rgba(239, 68, 68, 0.4); }
            50% { box-shadow: 0 10px 60px rgba(239, 68, 68, 0.6); }
        }
        @keyframes bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-10px); }
        }

        /* Paused System Banner */
        .paused-banner {
            background: #f59e0b;
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            text-align: center;
            font-weight: 600;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }
        .header p {
            opacity: 0.9;
            font-size: 1.1em;
        }
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: white;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .card h2 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        .stat {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .stat:last-child { border-bottom: none; }
        .stat-label {
            color: #666;
            font-weight: 500;
        }
        .stat-value {
            color: #333;
            font-weight: 600;
        }
        .status-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: 600;
        }
        .status-running { background: #10b981; color: white; }
        .status-completed { background: #3b82f6; color: white; }
        .status-pending { background: #f59e0b; color: white; }
        .status-failed { background: #ef4444; color: white; }
        .tasks-list {
            background: white;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .task-item {
            padding: 15px;
            border-left: 4px solid #667eea;
            background: #f9fafb;
            margin-bottom: 15px;
            border-radius: 5px;
        }
        .task-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .task-id {
            font-family: monospace;
            color: #666;
            font-size: 0.9em;
        }
        .task-details {
            color: #666;
            font-size: 0.95em;
        }

        /* PR Cards */
        .pr-card {
            background: white;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 20px;
            border-left: 5px solid #667eea;
        }
        .pr-card h3 {
            color: #667eea;
            margin-bottom: 12px;
            font-size: 1.2em;
        }
        .pr-number {
            font-family: monospace;
            background: #667eea;
            color: white;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.9em;
            margin-right: 8px;
        }
        .pr-meta {
            color: #666;
            font-size: 0.9em;
            margin-top: 8px;
        }
        .pr-actions {
            margin-top: 15px;
            display: flex;
            gap: 10px;
        }
        .pr-button {
            background: #667eea;
            color: white;
            padding: 10px 20px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            transition: background 0.2s;
        }
        .pr-button:hover {
            background: #5568d3;
        }

        .refresh-info {
            text-align: center;
            color: white;
            margin-top: 20px;
            opacity: 0.8;
        }
        .pulse {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        /* Mobile responsive */
        @media (max-width: 768px) {
            body { padding: 10px; }
            .cards { grid-template-columns: 1fr; }
            .pr-banner h2 { font-size: 1.3em; }
        }
    </style>
    <script>
        // Auto-refresh every 30 seconds to check for PR updates
        let refreshInterval = 30000;

        // Check if there are pending PRs - if so, refresh more frequently
        let hasPendingPRs = {{ 'true' if open_prs else 'false' }};
        if (hasPendingPRs) {
            refreshInterval = 15000; // 15 seconds when PRs are pending
            // Update page title to alert user
            document.title = '⚠️ PR READY - Evolution System';
        }

        setTimeout(() => location.reload(), refreshInterval);

        // Flash notification in title
        if (hasPendingPRs) {
            let originalTitle = document.title;
            let flashTitle = '🚨 ACTION REQUIRED 🚨';
            setInterval(() => {
                document.title = document.title === originalTitle ? flashTitle : originalTitle;
            }, 1000);
        }
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Context Foundry Evolution System</h1>
            <p>Autonomous Self-Improving AI Infrastructure</p>
        </div>

        <!-- PR Notification Banner -->
        {% if open_prs %}
        <div class="pr-banner">
            <h2>
                <span class="pr-banner-icon">🚨</span>
                Pull Request Ready for Review!
            </h2>
            <p>The Evolution System has created {{ open_prs|length }} PR(s) that need your approval.</p>
            <p style="margin-top: 10px;">The daemon is waiting for you to review and merge these PRs before continuing.</p>
            <a href="{{ open_prs[0].url }}" target="_blank" class="pr-banner-button">
                Review PR #{{ open_prs[0].number }} on GitHub →
            </a>
        </div>
        {% endif %}

        <!-- System Paused Banner -->
        {% if daemon_paused %}
        <div class="paused-banner">
            ⏸️ System Paused - Waiting for PR merge to continue
        </div>
        {% endif %}

        <div class="cards">
            <!-- Daemon Status -->
            <div class="card">
                <h2>⚙️ Daemon Status</h2>
                <div class="stat">
                    <span class="stat-label">Status</span>
                    <span class="stat-value">
                        <span class="status-badge status-{{ daemon_status }}">{{ daemon_status|upper }}</span>
                    </span>
                </div>
                <div class="stat">
                    <span class="stat-label">PID</span>
                    <span class="stat-value">{{ daemon_pid }}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Uptime</span>
                    <span class="stat-value">{{ daemon_uptime }}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Last Poll</span>
                    <span class="stat-value pulse">{{ last_poll }}</span>
                </div>
            </div>

            <!-- Task Queue Stats -->
            <div class="card">
                <h2>📋 Task Queue</h2>
                <div class="stat">
                    <span class="stat-label">Pending</span>
                    <span class="stat-value">{{ tasks_pending }}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Running</span>
                    <span class="stat-value">{{ tasks_running }}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Completed</span>
                    <span class="stat-value">{{ tasks_completed }}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Failed</span>
                    <span class="stat-value">{{ tasks_failed }}</span>
                </div>
            </div>

            <!-- Evolution Modes -->
            <div class="card">
                <h2>🧬 Evolution Modes</h2>
                <div class="stat">
                    <span class="stat-label">Self-Improvement</span>
                    <span class="stat-value">
                        <span class="status-badge status-running">ACTIVE</span>
                    </span>
                </div>
                <div class="stat">
                    <span class="stat-label">Chaos/Creative</span>
                    <span class="stat-value">
                        <span class="status-badge status-pending">READY</span>
                    </span>
                </div>
                <div class="stat">
                    <span class="stat-label">Research</span>
                    <span class="stat-value">
                        <span class="status-badge status-pending">READY</span>
                    </span>
                </div>
            </div>
        </div>

        <!-- Open Pull Requests -->
        {% if open_prs %}
        <div style="margin-bottom: 30px;">
            <h2 style="color: white; margin-bottom: 20px; text-align: center;">📋 Open Pull Requests ({{ open_prs|length }})</h2>
            {% for pr in open_prs %}
            <div class="pr-card">
                <h3>
                    <span class="pr-number">#{{ pr.number }}</span>
                    {{ pr.title }}
                </h3>
                <div class="pr-meta">
                    <strong>Branch:</strong> {{ pr.branch }} |
                    <strong>Created:</strong> {{ pr.created_at[:10] }} |
                    <strong>Author:</strong> {{ pr.user }}
                </div>
                <div class="pr-actions">
                    <a href="{{ pr.url }}" target="_blank" class="pr-button">Review on GitHub</a>
                    <a href="{{ pr.url }}/files" target="_blank" class="pr-button">View Changes</a>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <!-- Recent Tasks -->
        <div class="tasks-list">
            <h2 style="color: #667eea; margin-bottom: 20px;">🔄 Recent Tasks</h2>
            {% if tasks %}
                {% for task in tasks %}
                <div class="task-item">
                    <div class="task-header">
                        <span class="task-id">{{ task.id[:16] }}...</span>
                        <span class="status-badge status-{{ task.status }}">{{ task.status|upper }}</span>
                    </div>
                    <div class="task-details">
                        <strong>Type:</strong> {{ task.type }} |
                        <strong>Priority:</strong> {{ task.priority }} |
                        <strong>Created:</strong> {{ task.created_at }}
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <p style="color: #999; text-align: center; padding: 20px;">No tasks yet</p>
            {% endif %}
        </div>

        <div class="refresh-info">
            🔄 Auto-refreshing every {{ '15' if open_prs else '30' }} seconds{% if open_prs %} (faster while PRs pending){% endif %} | Current time: {{ current_time }}
        </div>
    </div>
</body>
</html>
"""

def get_db_path():
    """Get path to task queue database"""
    return Path.home() / ".context-foundry" / "evolution" / "task_queue.db"

def get_daemon_status():
    """Check if daemon is running"""
    try:
        pid_file = Path.home() / ".context-foundry" / "evolution" / "daemon.pid"
        if not pid_file.exists():
            return {'status': 'stopped', 'pid': 'N/A', 'uptime': 'N/A'}

        pid = pid_file.read_text().strip()

        # Check if process is running
        result = subprocess.run(['ps', '-p', pid], capture_output=True)
        if result.returncode != 0:
            return {'status': 'stopped', 'pid': 'N/A', 'uptime': 'N/A'}

        # Get uptime
        uptime_result = subprocess.run(['ps', '-p', pid, '-o', 'etime='], capture_output=True, text=True)
        uptime = uptime_result.stdout.strip() if uptime_result.returncode == 0 else 'N/A'

        return {'status': 'running', 'pid': pid, 'uptime': uptime}
    except Exception as e:
        return {'status': 'error', 'pid': f'Error: {e}', 'uptime': 'N/A'}

def get_task_stats():
    """Get task queue statistics"""
    db_path = get_db_path()
    if not db_path.exists():
        return {'pending': 0, 'running': 0, 'completed': 0, 'failed': 0}

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    stats = {}
    for status in ['pending', 'running', 'completed', 'failed']:
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", (status,))
        stats[status] = cursor.fetchone()[0]

    conn.close()
    return stats

def get_recent_tasks(limit=5):
    """Get recent tasks"""
    db_path = get_db_path()
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, type, status, priority, created_at
        FROM tasks
        ORDER BY created_at DESC
        LIMIT ?
    """, (limit,))

    tasks = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return tasks

@app.route('/')
def dashboard():
    """Main dashboard page with PR integration"""
    daemon = get_daemon_status()
    stats = get_task_stats()
    tasks = get_recent_tasks()
    open_prs = get_open_prs()

    # Check if daemon should be paused (has open PRs)
    daemon_paused = len(open_prs) > 0

    return render_template_string(
        DASHBOARD_HTML,
        daemon_status=daemon['status'],
        daemon_pid=daemon['pid'],
        daemon_uptime=daemon['uptime'],
        daemon_paused=daemon_paused,
        last_poll='Active' if daemon['status'] == 'running' else 'N/A',
        tasks_pending=stats['pending'],
        tasks_running=stats['running'],
        tasks_completed=stats['completed'],
        tasks_failed=stats['failed'],
        tasks=tasks,
        open_prs=open_prs,
        current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

@app.route('/api/status')
def api_status():
    """API endpoint for status (JSON) with PR integration"""
    daemon = get_daemon_status()
    stats = get_task_stats()
    tasks = get_recent_tasks()
    open_prs = get_open_prs()

    return jsonify({
        'daemon': daemon,
        'task_stats': stats,
        'recent_tasks': tasks,
        'open_prs': open_prs,
        'daemon_paused': len(open_prs) > 0,
        'github_owner': get_github_owner(),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/pr/<int:pr_number>/check_merged')
def check_pr_merged_api(pr_number):
    """API endpoint to check if a PR is merged"""
    is_merged = check_pr_merged(pr_number)
    return jsonify({
        'pr_number': pr_number,
        'merged': is_merged,
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("🌐 Starting Evolution System Web Dashboard...")
    print("📊 Dashboard: http://localhost:8765")
    print("🔌 API: http://localhost:8765/api/status")
    print("\n✨ Press Ctrl+C to stop\n")
    app.run(host='0.0.0.0', port=8765, debug=False)
