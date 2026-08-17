"""Точка входа: ``python -m core.tokenstat`` — отчёт по токенам за окно прогона.

Слой вывода (единственное место с ``print``). Точка отсчёта — файл, который скил пишет на старте
(``out/hw01/build_start.txt``: строки ``session=<путь>``, ``offset_lines=<N>``), либо явные аргументы.

Пример::

    python -m core.tokenstat --since out/hw01/build_start.txt --label hw01-h --out out/hw01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .transcript_token_meter import TranscriptTokenMeter


def _native_path(text: str) -> Path:
    """Путь из Git Bash (`/c/Users/...`) → `C:/Users/...`; прочие — как есть."""
    if len(text) > 3 and text[0] == "/" and text[2] == "/" and text[1].isalpha():
        return Path(f"{text[1].upper()}:{text[2:]}")
    return Path(text)


def _read_start_file(path: Path) -> tuple[Path | None, int, tuple[str, ...]]:
    """Разобрать ``build_start.txt``: session=…, offset_lines=…, далее — имена файлов агентов."""
    session: Path | None = None
    offset = 0
    agents: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("session="):
            session = _native_path(line.split("=", 1)[1].strip())
        elif line.startswith("offset_lines="):
            offset = int(line.split("=", 1)[1].strip())
        elif line.endswith(".jsonl"):
            agents.append(line)
    return session, offset, tuple(agents)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m core.tokenstat", description="отчёт по токенам за окно прогона")
    parser.add_argument("--since", type=Path, help="файл точки отсчёта (build_start.txt)")
    parser.add_argument("--session", type=Path, help="JSONL-транскрипт сессии (перекрывает --since)")
    parser.add_argument("--offset", type=int, help="смещение в строках (перекрывает --since)")
    parser.add_argument("--label", default="run", help="метка окна в отчёте")
    parser.add_argument("--out", type=Path, help="каталог для tokens_<дата>_<время>.md")
    args = parser.parse_args(argv)

    session: Path | None = None
    offset = 0
    agents: tuple[str, ...] = ()
    if args.since is not None:
        session, offset, agents = _read_start_file(args.since)
    if args.session is not None:
        session = args.session
    if args.offset is not None:
        offset = args.offset
    if session is None:
        parser.error("нужен --since <build_start.txt> или --session <файл.jsonl>")

    meter = TranscriptTokenMeter(session)
    meter.start_from(args.label, offset, agents)
    meter.stop()
    print(meter.report())
    if args.out is not None:
        print(f"записано: {meter.write(args.out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
