# Prompt 版本管理测试

import tempfile
import os
from app.services.prompt_registry import PromptRegistry


def make_registry():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return PromptRegistry(db_path=path)


def test_register_and_get_latest():
    registry = make_registry()
    pv = registry.register("test_prompt", "system text", "user template")
    assert pv.version == 1
    assert pv.system_prompt == "system text"

    latest = registry.get_latest("test_prompt")
    assert latest.version == 1


def test_register_same_content_no_new_version():
    registry = make_registry()
    registry.register("test_prompt", "system text", "user template")
    pv2 = registry.register("test_prompt", "system text", "user template")
    assert pv2.version == 1  # 不应创建新版本


def test_register_different_content_creates_new_version():
    registry = make_registry()
    registry.register("test_prompt", "v1 system", "v1 user")
    pv2 = registry.register("test_prompt", "v2 system", "v2 user")
    assert pv2.version == 2


def test_get_by_version():
    registry = make_registry()
    registry.register("test_prompt", "v1", "t1")
    registry.register("test_prompt", "v2", "t2")

    v1 = registry.get_by_version("test_prompt", 1)
    assert v1.system_prompt == "v1"

    v2 = registry.get_by_version("test_prompt", 2)
    assert v2.system_prompt == "v2"


def test_list_versions():
    registry = make_registry()
    registry.register("test_prompt", "v1", "t1")
    registry.register("test_prompt", "v2", "t2")
    registry.register("test_prompt", "v3", "t3")

    versions = registry.list_versions("test_prompt")
    assert len(versions) == 3
    assert versions[0]["version"] == 1
    assert versions[2]["version"] == 3


def test_rollback():
    registry = make_registry()
    registry.register("test_prompt", "v1", "t1")
    registry.register("test_prompt", "v2", "t2")

    rolled = registry.rollback("test_prompt", 1)
    assert rolled.version == 3  # 新版本号
    assert rolled.system_prompt == "v1"  # 内容来自 v1


def test_get_nonexistent_returns_none():
    registry = make_registry()
    assert registry.get_latest("nonexistent") is None
    assert registry.get_by_version("nonexistent", 1) is None


def test_metadata_stored():
    registry = make_registry()
    pv = registry.register("test", "s", "u", {"key": "value"})
    assert pv.metadata == {"key": "value"}
