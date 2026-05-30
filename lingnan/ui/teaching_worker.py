"""教研内容生成后台 Worker：调用 LLM，避免阻塞 UI。

镜像 ui/worker.py 的 DetectWorker 模式。失败时发 failed，由页面降级为模板填充。
"""

from __future__ import annotations

from PyQt5.QtCore import QThread, pyqtSignal

from ..core.llm_client import LLMClient


class TeachingWorker(QThread):
    finished = pyqtSignal(str)   # 生成的 Markdown
    failed = pyqtSignal(str)     # 失败消息（页面据此降级模板）

    def __init__(self, client: LLMClient, system: str, user: str):
        super().__init__()
        self.client = client
        self.system = system
        self.user = user

    def run(self):
        try:
            md = self.client.chat(self.system, self.user)
            self.finished.emit(md)
        except Exception as e:
            self.failed.emit(str(e))
