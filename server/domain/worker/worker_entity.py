"""
domain/worker/worker_entity.py

Worker 元信息与状态值对象。
"""

from dataclasses import dataclass, field

from server.domain.worker.capability_entity import CapabilityEntity


@dataclass
class WorkerMetaEntity:
    worker_id: str
    kind: str = "generic"
    label: str = ""
    version: str = ""
    platform: str = ""
    browser_type: str = ""
    headless: bool = True
    allowed_origins: list[str] = field(default_factory=list)
    max_sessions: int = 0
    max_screenshot_bytes: int = 0
    max_text_chars: int = 0
    max_html_chars: int = 0
    source: str = ""


@dataclass
class WorkerInfoEntity:
    worker_id: str
    label: str
    kind: str
    status: str
    registered_capabilities: list[CapabilityEntity] = field(default_factory=list)
    enabled_capability_names: list[str] = field(default_factory=list)
    version: str = ""
    platform: str = ""
    browser_type: str = ""
    headless: bool = True
    allowed_origins: list[str] = field(default_factory=list)
    max_sessions: int = 0
    max_screenshot_bytes: int = 0
    max_text_chars: int = 0
    max_html_chars: int = 0
    source: str = ""
    connected_at: str = ""
    last_seen_at: str = ""
    last_error: str = ""
