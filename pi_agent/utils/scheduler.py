# -*- coding: utf-8 -*-
from __future__ import annotations
import time, heapq, threading
from typing import Callable, Dict, Any, List, Tuple
from . import http

"""
一個本地排程器模組，用來定期從伺服器取得排程任務，
並在指定時間點執行這些任務。
"""

# 定義一個排程任務的資料結構。這是一個元組 (Tuple)，
# 包含四個元素：(執行時間戳, 排程ID, 動作名稱, 動作參數)。
Job = Tuple[int, int, str, Dict[str, Any]]  # (ts, id, action, payload)


class LocalScheduler:
    """
    本地排程器類別。
    它使用一個最小堆（min-heap）來儲存任務，確保最接近執行時間的任務總是在堆頂。
    透過一個獨立的執行緒來監聽和執行這些任務。
    """

    def __init__(self, run_action: Callable[[str, Dict[str, Any]], None]):
        """
        初始化 LocalScheduler。

        Args:
            run_action: 一個可呼叫的函式，用來實際執行排程任務。
                        它接受兩個參數：動作名稱 (action) 和參數 (payload)。
        """
        self._run_action = run_action
        self._heap: List[Job] = []  # 使用 list 模擬最小堆，儲存排程任務
        self._lock = threading.Lock()  # 用於保護多執行緒存取 _heap 時的同步鎖
        self._wakeup = threading.Event()  # 用於喚醒睡眠中的執行緒
        self._stop = False  # 停止執行緒的旗標
        # 建立一個獨立的執行緒來執行排程邏輯。daemon=True 確保主程式結束時這個執行緒也會終止。
        self._runner = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        """
        啟動排程器。
        """
        self._runner.start()

    def stop(self):
        """
        停止排程器。
        """
        self._stop = True
        self._wakeup.set()  # 喚醒執行緒，讓它能檢查 _stop 旗標並安全地退出。

    def refresh_from_server(self):
        """
        從伺服器獲取最新的排程任務清單，並將其添加到本地排程器中。
        """
        items = http.fetch_schedules()
        if not items:
            return

        with self._lock:  # 鎖住，以確保在更新堆時不會有其他執行緒同時存取
            # 用 set 來快速檢查排程 ID 是否已存在，避免重複加入
            existing = {jid for _, jid, _, _ in self._heap}
            for it in items:
                sid = int(it["id"])
                # 如果排程 ID 已經存在，就跳過
                if sid in existing:
                    continue

                # 解析排程資料
                ts = int(it["ts"])  # 時間戳 (timestamp)
                action = it["action"]
                payload = it.get("payload") or {}

                # 將新任務推入最小堆。heapq 會自動維持堆的結構，
                # 確保時間戳最小的任務總在堆頂。
                heapq.heappush(self._heap, (ts, sid, action, payload))

            # 喚醒 _loop 執行緒，讓它能立即檢查是否有新任務可以執行
            self._wakeup.set()

    def _loop(self):
        """
        排程器的主要執行循環，在獨立的執行緒中運行。
        它會不斷檢查堆頂的任務是否已到執行時間，並執行它。
        """
        while not self._stop:
            now = int(time.time())
            job: Job | None = None
            wait_for = 5  # 預設等待時間，如果沒有排程任務時，每隔 5 秒檢查一次

            with self._lock:  # 鎖住，確保存取 _heap 時的同步
                if self._heap:
                    ts, sid, action, payload = self._heap[0]  # 查看堆頂任務，但不移除
                    if ts <= now:
                        # 如果任務已到或已過執行時間，則將其從堆中移除
                        heapq.heappop(self._heap)
                        job = (ts, sid, action, payload)
                    else:
                        # 如果任務未到執行時間，則計算需要等待多久
                        wait_for = max(1, ts - now)

            if job:
                _, sid, action, payload = job
                ok = True
                err = ""
                try:
                    # 執行排程任務
                    self._run_action(action, payload)
                except Exception as e:
                    # 如果執行失敗，捕獲錯誤訊息
                    ok = False
                    err = str(e)
                try:
                    # 向伺服器回報任務執行結果（成功或失敗）
                    http.schedule_ack(sid, ok=ok, error=err)
                except Exception as e:
                    print("schedule ack failed:", e)
                # 任務執行完成後，立即重新循環檢查下一個任務
                continue

            # 如果沒有任務可以執行，或任務還沒到時間，則進入等待狀態。
            # _wakeup.wait() 會阻塞執行緒，直到被 set() 喚醒或超過 timeout 時間。
            self._wakeup.wait(timeout=wait_for)
            self._wakeup.clear()
