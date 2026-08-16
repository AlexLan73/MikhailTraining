#!/usr/bin/env python
"""Composition Root: CLI-запуск домашних заданий.

    python run_hw.py --list          # список всех ДЗ
    python run_hw.py hw01            # одно задание
    python run_hw.py --all           # все подряд
    python run_hw.py hw01 --seed 7   # свой сид
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

# запуск скриптом из корня — гарантируем импорт пакетов проекта
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import default_settings  # noqa: E402
from homework.registry import HomeworkReport, HomeworkTask, all_tasks, get_task  # noqa: E402


def _print_list() -> None:
    print("\nДомашние задания:")
    for task in all_tasks():
        print(f"  {task.hw_id:<8} {task.title}")
    print()


def _print_report(report: HomeworkReport) -> None:
    print(f"\n=== {report.hw_id} · {report.title} ===")
    for name, value in report.metrics.items():
        print(f"  {name:<20} {value:.4f}")
    for note in report.notes:
        print(f"  ⚠ {note}")
    print(f"  --- {report.seconds:.2f} c ---")


def _run(task: HomeworkTask, seed: int) -> HomeworkReport:
    settings = replace(default_settings(), seed=seed)
    report = task.run(task.build_context(settings))
    _print_report(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Запуск домашних заданий курса по ИИ")
    parser.add_argument("hw_id", nargs="?", help="идентификатор задания, напр. hw01")
    parser.add_argument("--list", action="store_true", help="показать список заданий")
    parser.add_argument("--all", action="store_true", help="прогнать все задания")
    parser.add_argument("--seed", type=int, default=default_settings().seed, help="сид (по умолчанию 42)")
    args = parser.parse_args(argv)

    if args.list or (not args.hw_id and not args.all):
        _print_list()
        return 0

    tasks = all_tasks() if args.all else [get_task(args.hw_id)]
    failed = 0
    for task in tasks:
        try:
            _run(task, args.seed)
        except Exception as exc:  # noqa: BLE001 — CLI: показать причину, не роняя остальные
            failed += 1
            print(f"\n❌ {task.hw_id}: {type(exc).__name__}: {exc}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
