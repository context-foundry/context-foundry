"""SPEC.yaml schema definitions and validation"""
from typing import List, Dict, Optional, Literal, Union
from pydantic import BaseModel, Field


class EndpointSpec(BaseModel):
    """API endpoint specification"""
    name: str
    method: str = "GET"
    path: str
    request: Optional[Dict] = None
    response: Dict
    example: Optional[Dict] = None


class ApiSpec(BaseModel):
    """API project specification"""
    kind: Literal["api"] = "api"
    service: str
    env: Dict[str, List[str]] = Field(default_factory=lambda: {"required": [], "optional": []})
    contract: Dict = Field(default_factory=dict)


class CommandSpec(BaseModel):
    """CLI command specification"""
    name: str
    args: List[str] = Field(default_factory=list)
    flags: List[Dict] = Field(default_factory=list)
    exit_codes: Dict[int, str] = Field(default_factory=lambda: {0: "success"})
    description: Optional[str] = None


class CliSpec(BaseModel):
    """CLI project specification"""
    kind: Literal["cli"] = "cli"
    binary: str
    env: Dict[str, List[str]] = Field(default_factory=lambda: {"required": [], "optional": []})
    commands: List[CommandSpec]


class PageSpec(BaseModel):
    """Web page specification"""
    path: str
    title_contains: Optional[str] = None
    status: int = 200
    elements: Optional[List[str]] = None


class WebSpec(BaseModel):
    """Web project specification"""
    kind: Literal["web"] = "web"
    base_url: str = "http://localhost:3000"
    env: Dict[str, List[str]] = Field(default_factory=lambda: {"required": [], "optional": []})
    pages: List[PageSpec]


# Union type for any spec
SpecType = Union[ApiSpec, CliSpec, WebSpec]


def validate_spec_yaml(spec_dict: Dict) -> SpecType:
    """Validate a SPEC.yaml dictionary against the appropriate schema.

    Args:
        spec_dict: Dictionary loaded from SPEC.yaml

    Returns:
        Validated spec object (ApiSpec, CliSpec, or WebSpec)

    Raises:
        ValueError: If kind is unknown or validation fails
    """
    kind = spec_dict.get("kind", "api")

    if kind == "api":
        return ApiSpec(**spec_dict)
    elif kind == "cli":
        return CliSpec(**spec_dict)
    elif kind == "web":
        return WebSpec(**spec_dict)
    else:
        raise ValueError(f"Unknown spec kind: {kind}")
