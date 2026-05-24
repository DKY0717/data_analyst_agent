# Schema Loader 测试文件
import pytest
from app.db.schema_loader import SchemaLoader

def test_schema_loader_get_tables():
    """测试获取表列表"""
    loader = SchemaLoader()
    tables = loader.get_tables()
    assert isinstance(tables, list)
    assert len(tables) > 0

def test_schema_loader_get_table_schema():
    """测试获取表结构"""
    loader = SchemaLoader()
    tables = loader.get_tables()
    if tables:
        table_name = tables[0]
        schema = loader.get_table_schema(table_name)
        assert "columns" in schema
        assert isinstance(schema["columns"], list)

def test_schema_loader_get_full_schema():
    """测试获取完整数据库结构"""
    loader = SchemaLoader()
    schema = loader.get_full_schema()
    assert "tables" in schema
    assert isinstance(schema["tables"], dict)