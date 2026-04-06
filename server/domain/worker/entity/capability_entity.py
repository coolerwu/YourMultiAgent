"""
domain/worker/entity/capability_entity.py

Worker Capability 值对象。
描述一个 Worker 能做什么事（函数签名 + 元数据）。
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParameterSchema:
    """单个参数的描述"""
    name: str
    type: str          # "str" | "int" | "bool" | "dict" | "list"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class CapabilityEntity:
    """
    一个可调用的 Worker 能力。
    由 @capability 装饰器从函数签名自动生成。
    """
    name: str                                    # 唯一标识，如 "read_file"
    description: str                             # 给 LLM 看的功能描述
    parameters: list[ParameterSchema] = field(default_factory=list)
    worker_id: str = "local"                     # 归属的 Worker（初期固定 local）

    def to_tool_schema(self) -> dict:
        """转为 LLM tool_use 格式（兼容 Anthropic / OpenAI）"""
        properties = {}
        required = []
        for p in self.parameters:
            properties[p.name] = {"type": p.type, "description": p.description}
            if p.default is not None:
                properties[p.name]["default"] = p.default
            if p.required:
                required.append(p.name)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }
