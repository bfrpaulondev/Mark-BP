"""Task store contract + in-memory implementation (ANT-278 F3).

The Protocol is the persistence boundary: an in-memory store today, a
Supabase/Postgres or queue-backed store later — tasks survive restarts
because the whole state round-trips through dictionaries.
"""

from __future__ import annotations

import threading
from typing import Protocol

from tasks.model import Task


class TaskStore(Protocol):
    def save_task(self, task: Task) -> None: ...

    def get_task(self, task_id: str, owner_id: str) -> Task | None: ...

    def list_tasks(self, owner_id: str, *, non_terminal_only: bool = False) -> list[Task]: ...

    def delete_task(self, task_id: str, owner_id: str) -> bool: ...


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, Task] = {}

    # -.-.-.-
    def save_task(self, task: Task) -> None:
        with self._lock:
            self._tasks[task.id] = task

    # -.-.-.-
    def get_task(self, task_id: str, owner_id: str) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
        if task is None or task.owner_id != owner_id:
            return None
        return task

    # -.-.-.-
    def list_tasks(self, owner_id: str, *, non_terminal_only: bool = False) -> list[Task]:
        with self._lock:
            tasks = list(self._tasks.values())
        tasks = [task for task in tasks if task.owner_id == owner_id]
        if non_terminal_only:
            tasks = [task for task in tasks if not task.is_terminal]
        return sorted(tasks, key=lambda task: task.created_at)

    # -.-.-.-
    def delete_task(self, task_id: str, owner_id: str) -> bool:
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None or task.owner_id != owner_id:
                return False
            del self._tasks[task_id]
            return True

    # -.-.-.-
    def to_dicts(self) -> list[dict]:
        """Snapshot for restart simulation/tests."""
        with self._lock:
            return [task.to_dict() for task in self._tasks.values()]

    def load_dicts(self, snapshots: list[dict]) -> None:
        for snapshot in snapshots:
            self.save_task(Task.from_dict(snapshot))
