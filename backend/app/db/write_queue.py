# DuckDB 写队列
# 将并发写入串行化，避免 DuckDB 单写锁导致的冲突

import queue
import threading
from typing import Any, Optional


class WriteQueue:
    """串行写入队列

    DuckDB 同一时间只允许一个写连接。WriteQueue 将所有写操作
    排入队列，由专用线程依次执行，避免并发写入冲突。

    用法：
        write_queue = WriteQueue()

        # 同步写入（阻塞直到执行完成）
        result = write_queue.execute(conn, "INSERT INTO t VALUES (?)", [1])

        # 异步写入（不等待结果）
        write_queue.execute_async(conn, "INSERT INTO t VALUES (?)", [1])
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _run(self):
        """专用写线程，从队列中取出任务并执行"""
        while True:
            item = self._queue.get()
            if item is None:
                break
            conn, sql, params, result_future, error_future = item
            try:
                if params:
                    result = conn.execute(sql, params)
                else:
                    result = conn.execute(sql)
                if result_future:
                    result_future.set_result(result)
            except Exception as e:
                if error_future:
                    error_future.set_exception(e)
            finally:
                self._queue.task_done()

    def execute_sync(self, conn: Any, sql: str, params: Optional[list] = None) -> Any:
        """同步写入：阻塞直到执行完成"""
        import concurrent.futures
        result_future = concurrent.futures.Future()
        error_future = concurrent.futures.Future()
        self._queue.put((conn, sql, params, result_future, error_future))

        # 等待结果
        try:
            return result_future.result(timeout=30)
        except concurrent.futures.TimeoutError:
            raise TimeoutError("写队列超时")
        except Exception:
            raise

    def execute_async(self, conn: Any, sql: str, params: Optional[list] = None) -> None:
        """异步写入：不等待结果"""
        self._queue.put((conn, sql, params, None, None))

    def size(self) -> int:
        """返回队列中待处理的写入数量"""
        return self._queue.qsize()


# 全局写队列实例
write_queue = WriteQueue()
