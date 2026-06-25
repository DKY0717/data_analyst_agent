# 写队列测试

import time
import threading
from app.db.write_queue import WriteQueue


def test_write_queue_basic():
    q = WriteQueue()
    # 写队列应该能正常创建
    assert q.size() == 0


def test_write_queue_size():
    q = WriteQueue()
    assert q.size() == 0
