# A/B 测试框架测试

import tempfile
import os
from app.services.ab_test import ABTestRegistry, ABTest, ABTestVariant


def make_registry():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return ABTestRegistry(db_path=path)


def test_register_and_list():
    registry = make_registry()
    test = ABTest(
        test_id="test_1",
        description="测试 prompt v1 vs v2",
        variants=[
            ABTestVariant("control", "generate_sql", 1, weight=1.0),
            ABTestVariant("treatment", "generate_sql", 2, weight=1.0),
        ],
    )
    registry.register(test)

    tests = registry.list_tests()
    assert len(tests) == 1
    assert tests[0]["test_id"] == "test_1"
    assert tests[0]["variants"] == ["control", "treatment"]


def test_route_consistent():
    registry = make_registry()
    test = ABTest(
        test_id="test_1",
        description="test",
        variants=[
            ABTestVariant("control", "generate_sql", 1, weight=1.0),
            ABTestVariant("treatment", "generate_sql", 2, weight=1.0),
        ],
    )
    registry.register(test)

    # 同一问题应始终路由到同一变体
    q = "查询销售额最高的商品"
    v1 = registry.route("test_1", q)
    v2 = registry.route("test_1", q)
    assert v1.name == v2.name


def test_route_disabled_test():
    registry = make_registry()
    test = ABTest(
        test_id="test_1",
        description="test",
        variants=[ABTestVariant("control", "generate_sql", 1)],
        enabled=False,
    )
    registry.register(test)
    assert registry.route("test_1", "question") is None


def test_route_nonexistent_test():
    registry = make_registry()
    assert registry.route("nonexistent", "question") is None


def test_record_and_report():
    registry = make_registry()
    test = ABTest(
        test_id="test_1",
        description="test",
        variants=[
            ABTestVariant("control", "generate_sql", 1),
            ABTestVariant("treatment", "generate_sql", 2),
        ],
    )
    registry.register(test)

    # 记录一些结果
    registry.record("test_1", "control", "q1", True, latency_ms=100)
    registry.record("test_1", "control", "q2", True, latency_ms=120)
    registry.record("test_1", "control", "q3", False, latency_ms=150)
    registry.record("test_1", "treatment", "q1", True, latency_ms=90)
    registry.record("test_1", "treatment", "q2", True, latency_ms=80)
    registry.record("test_1", "treatment", "q3", True, latency_ms=85)

    report = registry.get_report("test_1")

    assert report["test_id"] == "test_1"
    assert report["variants"]["control"]["total_requests"] == 3
    assert report["variants"]["control"]["success_count"] == 2
    assert report["variants"]["control"]["success_rate"] == 2 / 3
    assert report["variants"]["treatment"]["total_requests"] == 3
    assert report["variants"]["treatment"]["success_count"] == 3
    assert report["variants"]["treatment"]["success_rate"] == 1.0

    # 验证提升度计算
    lift = report["variants"]["_lift"]
    assert lift["from"] == "control"
    assert lift["to"] == "treatment"
    assert lift["success_rate_lift"] > 0  # treatment 优于 control


def test_weighted_routing():
    registry = make_registry()
    test = ABTest(
        test_id="test_1",
        description="test",
        variants=[
            ABTestVariant("control", "generate_sql", 1, weight=9.0),
            ABTestVariant("treatment", "generate_sql", 2, weight=1.0),
        ],
    )
    registry.register(test)

    # 大量请求，90% 应该走 control
    results = {}
    for i in range(1000):
        v = registry.route("test_1", f"question_{i}")
        results[v.name] = results.get(v.name, 0) + 1

    # control 应该占大多数（约 90%）
    assert results.get("control", 0) > 800
    assert results.get("treatment", 0) > 50


def test_empty_report():
    registry = make_registry()
    report = registry.get_report("nonexistent")
    assert report["variants"] == {}
