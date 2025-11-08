"""
MCP Tools for Context Foundry Evolution System (CFES)
These tools extend the main MCP server with evolution capabilities.
"""

import json
import os
import psutil
from pathlib import Path
from typing import Optional, Dict, List

# Lazy imports to avoid circular dependencies
_task_queue = None
_daemon = None


def get_task_queue():
    """Get or create TaskQueueManager instance"""
    global _task_queue
    if _task_queue is None:
        from tools.evolution.task_queue import TaskQueueManager
        _task_queue = TaskQueueManager()
    return _task_queue


def get_daemon():
    """Get or create EvolutionDaemon instance"""
    global _daemon
    if _daemon is None:
        from tools.evolution.daemon import EvolutionDaemon
        _daemon = EvolutionDaemon()
    return _daemon


def create_evolution_task_impl(
    task_type: str,
    target_project: Optional[str] = None,
    pattern_id: Optional[str] = None,
    priority: int = 5,
    params: Optional[Dict] = None
) -> str:
    """
    Create evolution task implementation
    
    Args:
        task_type: Type ('self_improvement', 'chaos_creative', 'research', 'apply_pattern', 'validate')
        target_project: Optional project path
        pattern_id: Optional pattern ID
        priority: Priority 1-10
        params: Additional parameters
    """
    try:
        queue = get_task_queue()
        
        task_params = params or {}
        if target_project:
            task_params['target_project'] = target_project
        if pattern_id:
            task_params['pattern_id'] = pattern_id
        
        task_id = queue.create_task(
            task_type=task_type,
            params=task_params,
            priority=priority
        )
        
        return json.dumps({
            "success": True,
            "task_id": task_id,
            "status": "pending",
            "message": f"Evolution task {task_id} created successfully"
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def get_evolution_tasks_impl(status: str = "pending", limit: int = 50) -> str:
    """List evolution tasks"""
    try:
        queue = get_task_queue()
        tasks = queue.list_tasks(
            status=None if status == 'all' else status,
            limit=limit
        )
        
        return json.dumps({
            "success": True,
            "count": len(tasks),
            "tasks": [task.to_dict() for task in tasks]
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def start_evolution_daemon_impl(config_path: Optional[str] = None) -> str:
    """Start evolution daemon"""
    try:
        daemon = get_daemon()
        
        if daemon.is_running():
            return json.dumps({
                "success": False,
                "message": "Daemon is already running",
                "pid": daemon.get_pid()
            }, indent=2)
        
        # Note: In full implementation, would fork/daemonize here
        return json.dumps({
            "success": True,
            "message": "Daemon start command issued (run daemon.py start for full daemonization)",
            "note": "Use 'python3 tools/evolution/daemon.py start' to fully daemonize"
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def stop_evolution_daemon_impl(graceful: bool = True) -> str:
    """Stop evolution daemon"""
    try:
        daemon = get_daemon()
        
        if not daemon.is_running():
            return json.dumps({
                "success": False,
                "message": "Daemon is not running"
            }, indent=2)
        
        pid = daemon.get_pid()
        if pid:
            os.kill(pid, 15)  # SIGTERM
            return json.dumps({
                "success": True,
                "message": f"Sent stop signal to daemon (PID: {pid})"
            }, indent=2)
        else:
            return json.dumps({
                "success": False,
                "message": "Could not determine daemon PID"
            }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def get_daemon_status_impl() -> str:
    """Get daemon status"""
    try:
        daemon = get_daemon()
        queue = get_task_queue()
        
        status = {
            "running": daemon.is_running(),
            "pid": daemon.get_pid() if daemon.is_running() else None,
            "uptime_seconds": daemon.get_uptime() if daemon.is_running() else 0,
            "queue_size": queue.count_pending(),
            "completed_tasks": queue.count_completed(),
            "failed_tasks": queue.count_failed(),
            "resource_usage": {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_mb": psutil.virtual_memory().used / (1024**2)
            }
        }
        
        return json.dumps({"success": True, "status": status}, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def register_project_impl(project_path: str, project_type: str, metadata: Optional[Dict] = None) -> str:
    """Register project in registry"""
    try:
        queue = get_task_queue()
        queue.register_project(
            path=project_path,
            project_type=project_type,
            metadata=metadata or {}
        )
        
        return json.dumps({
            "success": True,
            "message": f"Project registered: {project_path}"
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def apply_pattern_to_project_impl(project_path: str, pattern_id: str) -> str:
    """Create task to apply pattern to project"""
    try:
        queue = get_task_queue()
        task_id = queue.create_task(
            task_type='apply_pattern',
            params={'project_path': project_path, 'pattern_id': pattern_id},
            priority=7
        )
        
        return json.dumps({
            "success": True,
            "task_id": task_id,
            "message": f"Pattern application task created: {task_id}"
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def validate_project_health_impl(project_path: str) -> str:
    """Create validation task"""
    try:
        queue = get_task_queue()
        task_id = queue.create_task(
            task_type='validate',
            params={'project_path': project_path},
            priority=8
        )
        
        return json.dumps({
            "success": True,
            "task_id": task_id,
            "message": f"Validation task created: {task_id}"
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def register_agent_impl(agent_name: str, agent_url: Optional[str] = None, capabilities: Optional[List[str]] = None) -> str:
    """Register agent in network"""
    try:
        queue = get_task_queue()
        agent_id = queue.register_agent(
            name=agent_name,
            url=agent_url,
            capabilities=capabilities or []
        )
        
        return json.dumps({
            "success": True,
            "agent_id": agent_id,
            "message": f"Agent registered: {agent_name}"
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def send_agent_message_impl(target_agent: str, message_type: str, payload: Dict) -> str:
    """Send message to another agent"""
    try:
        from tools.evolution.agent_protocol import AgentProtocol
        protocol = AgentProtocol(agent_name="cfes")
        
        protocol.send_message(
            target=target_agent,
            message_type=message_type,
            payload=payload
        )
        
        return json.dumps({
            "success": True,
            "message": f"Message sent to {target_agent}"
        }, indent=2)
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)}, indent=2)
