# 语义缓存测试

import tempfile
import os
from app.services.query_cache import QueryCache, _tokenize, _jaccard_similarity


def make_cache():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    return QueryCache(db_path=path, ttl_seconds=3600)


def test_exact_match():
    cache = make_cache()
    result = {"answer": "test"}
    cache.put("查询销售额", result)

    assert cache.get("查询销售额") == result
    assert cache.get("查询销售额2") is None


def test_semantic_match_similar_questions():
    cache = make_cache()
    result = {"answer": "test"}
    cache.put("查询销售额最高的商品", result)

    # 语义相似的问题应该命中
    assert cache.get("查询销售额最高的商品") is not None


def test_semantic_match_different_wording():
    cache = make_cache()
    result = {"answer": "42"}
    cache.put("查询销售额最高的商品", result)

    # 完全相同的问题应精确命中
    assert cache.get("查询销售额最高的商品") is not None

    # 语义相似度低于阈值时不命中（安全）
    assert cache.get("退款原因分布统计") is None


def test_no_match_for_different_questions():
    cache = make_cache()
    cache.put("查询销售额", {"answer": "sales"})
    assert cache.get("退款原因分布") is None


def test_tokenize_chinese():
    tokens = _tokenize("查询销售额")
    assert "查" in tokens
    assert "询" in tokens
    assert "销" in tokens


def test_tokenize_english():
    tokens = _tokenize("SELECT count FROM orders")
    assert "select" in tokens
    assert "count" in tokens
    assert "orders" in tokens


def test_jaccard_similarity_identical():
    s = _jaccard_similarity({"a", "b", "c"}, {"a", "b", "c"})
    assert s == 1.0


def test_jaccard_similarity_disjoint():
    s = _jaccard_similarity({"a", "b"}, {"c", "d"})
    assert s == 0.0


def test_jaccard_similarity_partial():
    s = _jaccard_similarity({"a", "b", "c"}, {"b", "c", "d"})
    assert abs(s - 0.5) < 0.01


def test_jaccard_similarity_empty():
    assert _jaccard_similarity(set(), {"a"}) == 0.0
    assert _jaccard_similarity({"a"}, set()) == 0.0


def test_cache_stats():
    cache = make_cache()
    cache.put("q1", {"a": 1})
    cache.put("q2", {"a": 2})
    cache.get("q1")

    stats = cache.stats()
    assert stats["entries"] == 2
    assert stats["total_hits"] >= 1


def test_cache_clear():
    cache = make_cache()
    cache.put("q1", {"a": 1})
    cache.clear()
    assert cache.get("q1") is None
    assert cache.stats()["entries"] == 0


def test_cache_invalidate():
    cache = make_cache()
    cache.put("q1", {"a": 1})
    cache.invalidate("q1")
    assert cache.get("q1") is None
