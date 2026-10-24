"""Хранилище файлов клиентов (план, раздел 9: интерфейс Storage, чтобы потом подключить S3).

Сейчас — локальный каталог (в Docker — volume `uploads`). Имя на диске — UUID: исходное имя
файла хранится только в БД и в путь не попадает.
"""

from functools import lru_cache
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.config import get_settings


class Storage(Protocol):
    def save(self, content: bytes) -> str:
        """Сохраняет содержимое, возвращает ключ."""
        ...

    def load(self, key: str) -> bytes | None:
        """Содержимое по ключу или None, если файла нет."""
        ...

    def delete(self, key: str) -> None:
        """Удаляет файл; нет файла — ничего не делает."""
        ...


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self._root = root

    def save(self, content: bytes) -> str:
        self._root.mkdir(parents=True, exist_ok=True)
        key = uuid4().hex
        (self._root / key).write_bytes(content)
        return key

    def load(self, key: str) -> bytes | None:
        path = self._root / key
        # Ключи — только наши hex-UUID: никаких «../» и абсолютных путей.
        if not key.isalnum() or not path.is_file():
            return None
        return path.read_bytes()

    def delete(self, key: str) -> None:
        if key.isalnum():
            (self._root / key).unlink(missing_ok=True)


@lru_cache
def get_storage() -> LocalStorage:
    return LocalStorage(get_settings().uploads_dir)
