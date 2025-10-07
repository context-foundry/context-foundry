#!/usr/bin/env python3
"""
Data models for multi-agent orchestration.

Based on Anthropic's multi-agent research system architecture.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class SubagentTask:
    """Task definition for a subagent."""
    id: str
    type: str  # 'scout', 'builder', 'validator'
    objective: str
    output_format: str
    tools: List[str]
    sources: List[str] = field(default_factory=list)
    boundaries: str = ""
    priority: int = 1
    dependencies: List[str] = field(default_factory=list)  # IDs of tasks that must complete first


@dataclass
class WorkflowPlan:
    """Complete workflow plan from Lead Orchestrator."""
    complexity_assessment: str
    scout_tasks: List[SubagentTask]
    architect_strategy: str
    builder_tasks: List[SubagentTask]
    validation_tasks: List[SubagentTask]
    estimated_duration: str
    parallelization_strategy: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'complexity_assessment': self.complexity_assessment,
            'scout_tasks': [task.__dict__ for task in self.scout_tasks],
            'architect_strategy': self.architect_strategy,
            'builder_tasks': [task.__dict__ for task in self.builder_tasks],
            'validation_tasks': [task.__dict__ for task in self.validation_tasks],
            'estimated_duration': self.estimated_duration,
            'parallelization_strategy': self.parallelization_strategy
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkflowPlan':
        """Create from dictionary."""
        return cls(
            complexity_assessment=data.get('complexity_assessment', ''),
            scout_tasks=[SubagentTask(**task) for task in data.get('scout_tasks', [])],
            architect_strategy=data.get('architect_strategy', ''),
            builder_tasks=[SubagentTask(**task) for task in data.get('builder_tasks', [])],
            validation_tasks=[SubagentTask(**task) for task in data.get('validation_tasks', [])],
            estimated_duration=data.get('estimated_duration', ''),
            parallelization_strategy=data.get('parallelization_strategy', '')
        )


@dataclass
class SubagentResult:
    """Result from a subagent execution."""
    task_id: str
    task_type: str
    success: bool
    findings: Optional[str] = None
    files_written: List[str] = field(default_factory=list)
    token_usage: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'success': self.success,
            'findings': self.findings,
            'files_written': self.files_written,
            'token_usage': self.token_usage,
            'error': self.error,
            'metadata': self.metadata
        }


@dataclass
class PhaseResult:
    """Result from a complete phase (scout, architect, builder, validation)."""
    phase_name: str
    success: bool
    subagent_results: List[SubagentResult]
    compressed_summary: Optional[str] = None
    total_tokens: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'phase_name': self.phase_name,
            'success': self.success,
            'subagent_results': [r.to_dict() for r in self.subagent_results],
            'compressed_summary': self.compressed_summary,
            'total_tokens': self.total_tokens,
            'duration_seconds': self.duration_seconds,
            'error': self.error
        }
