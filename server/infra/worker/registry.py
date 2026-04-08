"""
infra/worker/registry.py

@capability 装饰器 + 自动扫描注册机制。

用法：
    @capability("read_file", "读取指定路径的文件内容")
    async def read_file(path: str) -> str:
        ...

启动时调用 scan_handlers() 即可自动发现所有 handlers/ 下的 capability。
"""

import importlib
import inspect
import pkgutil
from typing import Any, Callable

from server.domain.worker.capability_entity import CapabilityEntity, ParameterSchema

# 全局注册表：capability_name → (CapabilityEntity, 函数)
_REGISTRY: dict[str, tuple[CapabilityEntity, Callable]] = {}

# Python type → JSON Schema type 映射
_TYPE_MAP = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "dict": "object",
    "list": "array",
    "Any": "string",  # fallback
}


def capability(name: str, description: str):
    """
    装饰器：将函数注册为 Worker capability。
    自动从函数签名提取参数 schema。
    """
    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)
        params = []
        for param_name, param in sig.parameters.items():
            ann = param.annotation
            type_str = ann.__name__ if hasattr(ann, "__name__") else str(ann)
            json_type = _TYPE_MAP.get(type_str, "string")
            has_default = param.default is not inspect.Parameter.empty
            params.append(ParameterSchema(
                name=param_name,
                type=json_type,
                description=f"{param_name} 参数",
                required=not has_default,
                default=param.default if has_default else None,
            ))
        entity = CapabilityEntity(name=name, description=description, parameters=params)
        _REGISTRY[name] = (entity, fn)
        return fn
    return decorator


def scan_handlers(package: str = "server.infra.worker.handlers") -> None:
    """
    扫描 handlers 包下所有模块，触发 @capability 装饰器注册。
    在应用启动时调用一次即可。
    """
    pkg = importlib.import_module(package)
    pkg_path = pkg.__path__  # type: ignore[attr-defined]
    for _, module_name, _ in pkgutil.iter_modules(pkg_path):
        importlib.import_module(f"{package}.{module_name}")


def get_all_capabilities() -> list[CapabilityEntity]:
    return [entity for entity, _ in _REGISTRY.values()]


async def invoke(name: str, params: dict[str, Any], context: dict[str, Any] | None = None) -> Any:
    """
    调用已注册的 capability。
    context 用于运行时注入，目前支持：
      {"work_dir": "/abs/path/agentA/"}  — 文件操作的沙箱根目录
    """
    if name not in _REGISTRY:
        raise ValueError(f"未知 capability: {name}")
    _, fn = _REGISTRY[name]
    # 若函数声明了 _context 参数，则注入 context
    sig = inspect.signature(fn)
    if "_context" in sig.parameters:
        merged = dict(params)
        merged["_context"] = context or {}
        if inspect.iscoroutinefunction(fn):
            return await fn(**merged)
        return fn(**merged)
    if inspect.iscoroutinefunction(fn):
        return await fn(**params)
    return fn(**params)
