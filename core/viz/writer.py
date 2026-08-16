"""Запись графиков на диск. Рисование (что на графике) — дело стратегии-визуализатора,
запись (куда и чем) — дело `FigureWriter` (SRP).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def matplotlib_available() -> bool:
    """Есть ли matplotlib в среде (дома может не быть — ветка под SkipTest)."""
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return False
    return True


class FigureWriter:
    """Сохраняет `matplotlib.Figure` в каталог, создавая его при необходимости."""

    def __init__(self, out_dir: Path, *, dpi: int = 120) -> None:
        self._out_dir = out_dir
        self._dpi = dpi

    def save(self, figure: Any, name: str) -> Path:
        """Сохранить фигуру как `<out_dir>/<name>` и закрыть её (не течём памятью)."""
        self._out_dir.mkdir(parents=True, exist_ok=True)
        path = self._out_dir / name
        figure.savefig(path, dpi=self._dpi, bbox_inches="tight")
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            return path
        plt.close(figure)
        return path
