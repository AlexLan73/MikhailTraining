"""`DataContext` — единая точка доступа к данным и артефактам (Facade).

ДЗ не знает про пути: спрашивает контекст. Загрузчики — стандартная библиотека,
чтобы базовые задания работали без numpy/pandas.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from core.config import ProjectPaths


class DatasetMissingError(FileNotFoundError):
    """Датасет не скачан. Сообщение должно говорить ОТКУДА его взять (правило 08)."""


class DataContext:
    """Читает датасеты из `data/`, пишет артефакты в `out/<hw_id>/`."""

    def __init__(self, paths: ProjectPaths, hw_id: str) -> None:
        self._paths = paths
        self._hw_id = hw_id

    # --- пути ---------------------------------------------------------------

    @property
    def data_dir(self) -> Path:
        return self._paths.data

    @property
    def out_dir(self) -> Path:
        return self._paths.out_for(self._hw_id)

    def require(self, name: str, *, source: str = "") -> Path:
        """Вернуть путь к датасету или бросить понятную ошибку со ссылкой на источник."""
        path = self._paths.data_for(name)
        if not path.exists():
            hint = f" Скачать: {source}" if source else ""
            raise DatasetMissingError(f"нет датасета data/{name}.{hint}")
        return path

    # --- чтение -------------------------------------------------------------

    def read_csv(self, name: str, *, source: str = "", delimiter: str = ",") -> list[dict[str, str]]:
        """CSV с заголовком → список словарей (строки как есть, без приведения типов)."""
        path = self.require(name, source=source)
        with path.open("r", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh, delimiter=delimiter))

    def read_json(self, name: str, *, source: str = "") -> Any:
        path = self.require(name, source=source)
        return json.loads(path.read_text(encoding="utf-8"))

    # --- запись -------------------------------------------------------------

    def write_json(self, name: str, payload: Any) -> Path:
        """Сохранить артефакт в `out/<hw_id>/<name>` (UTF-8, читаемый отступ)."""
        path = self.out_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_text(self, name: str, text: str) -> Path:
        path = self.out_dir / name
        path.write_text(text, encoding="utf-8")
        return path
