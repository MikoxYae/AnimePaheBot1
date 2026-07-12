#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

"""Real asynchronous download queue with concurrency limits.

Background workers live inside the running bot process. Handlers call
`download_queue.enqueue(...)` and return immediately -- Pyrogram handlers
never block waiting for a download to finish.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from config import MAX_CONCURRENT_DOWNLOADS, MAX_DOWNLOADS_PER_USER, MAX_QUEUE_SIZE
from helper.logger import log


@dataclass
class _Task:
    task_id: str
    user_id: int
    username: str
    dedupe_key: str
    run: Callable[[], Awaitable[None]]


class DownloadQueue:
    """Bounded, deduplicated async download queue with per-user fairness."""

    def __init__(self):
        self._queue: "asyncio.Queue[_Task]" = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        self._lock = asyncio.Lock()
        self._active_dedupe_keys: set[str] = set()
        self._per_user_active: dict[int, int] = {}
        self._user_task_counts: dict[str, int] = {}  # username -> queued+active
        self._workers: list[asyncio.Task] = []

    def queue_size(self) -> int:
        return self._queue.qsize()

    def active_summary(self) -> list[tuple[str, int]]:
        """Per-username count of queued+active downloads, for /queue."""
        return sorted(self._user_task_counts.items(), key=lambda kv: -kv[1])

    async def is_duplicate(self, dedupe_key: str) -> bool:
        async with self._lock:
            return dedupe_key in self._active_dedupe_keys

    async def enqueue(
        self,
        user_id: int,
        username: str,
        dedupe_key: str,
        run: Callable[[], Awaitable[None]],
    ) -> "tuple[bool, Optional[int], Optional[str]]":
        """Try to enqueue a task.

        Returns (accepted, queue_position, reason). `reason` is set to
        "duplicate" or "full" when not accepted.
        """
        async with self._lock:
            if dedupe_key in self._active_dedupe_keys:
                return False, None, "duplicate"
            if self._queue.qsize() >= MAX_QUEUE_SIZE:
                return False, None, "full"
            self._active_dedupe_keys.add(dedupe_key)
            self._user_task_counts[username] = self._user_task_counts.get(username, 0) + 1
            position = self._queue.qsize() + 1

        task = _Task(
            task_id=str(uuid.uuid4()),
            user_id=user_id,
            username=username,
            dedupe_key=dedupe_key,
            run=run,
        )
        await self._queue.put(task)
        return True, position, None

    def start(self, worker_count: Optional[int] = None) -> "list[asyncio.Task]":
        if self._workers:
            return self._workers
        count = worker_count or MAX_CONCURRENT_DOWNLOADS
        self._workers = [
            asyncio.create_task(self._worker(i), name=f"download-queue-worker-{i}")
            for i in range(count)
        ]
        log.info("Started %d download queue worker(s)", count)
        return self._workers

    async def stop(self) -> None:
        for worker in self._workers:
            worker.cancel()
        for worker in self._workers:
            try:
                await worker
            except asyncio.CancelledError:
                pass
        self._workers = []

    async def _release(self, task: "_Task") -> None:
        async with self._lock:
            self._per_user_active[task.user_id] = max(
                0, self._per_user_active.get(task.user_id, 1) - 1
            )
            self._active_dedupe_keys.discard(task.dedupe_key)
            remaining = self._user_task_counts.get(task.username, 1) - 1
            if remaining <= 0:
                self._user_task_counts.pop(task.username, None)
            else:
                self._user_task_counts[task.username] = remaining

    async def _worker(self, index: int) -> None:
        while True:
            task = await self._queue.get()
            try:
                # Respect the per-user concurrency limit without blocking
                # everyone else: requeue this task and move on to the next
                # one if this user is already at their limit.
                async with self._lock:
                    busy = (
                        self._per_user_active.get(task.user_id, 0)
                        >= MAX_DOWNLOADS_PER_USER
                    )
                if busy:
                    await asyncio.sleep(1)
                    await self._queue.put(task)
                    continue

                async with self._lock:
                    self._per_user_active[task.user_id] = (
                        self._per_user_active.get(task.user_id, 0) + 1
                    )

                async with self._semaphore:
                    try:
                        await task.run()
                    except Exception:
                        log.exception("Download task %s failed", task.task_id)
                    finally:
                        await self._release(task)
            finally:
                self._queue.task_done()


download_queue = DownloadQueue()
