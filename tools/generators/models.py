"""
Data models for Context Foundry Evolution System.

Contains the Finding class used by BacklogGenerator for GitHub issue creation.
"""

from typing import List, Dict, Optional


class Finding:
    """Represents a discovered issue or enhancement"""

    def __init__(
        self,
        title: str,
        finding_type: str,  # 'bug', 'security', 'performance', 'enhancement', 'debt'
        priority: str,  # 'P0', 'P1', 'P2', 'P3', 'P4'
        category: List[str],
        description: str,
        file_path: str = None,
        line_number: int = None,
        evidence: str = None,
        effort: str = "medium",
    ):  # 'small', 'medium', 'large'
        self.title = title
        self.finding_type = finding_type
        self.priority = priority
        self.category = category
        self.description = description
        self.file_path = file_path
        self.line_number = line_number
        self.evidence = evidence
        self.effort = effort
        self.research: Optional[Dict] = None  # AI analysis results
        self.architectural_analysis: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "type": self.finding_type,
            "priority": self.priority,
            "category": self.category,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "evidence": self.evidence,
            "effort": self.effort,
            "research": self.research,
            "architectural_analysis": self.architectural_analysis,
        }
