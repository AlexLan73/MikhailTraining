#!/usr/bin/env python
"""Агрегатор всех тестовых наборов (🚫 pytest — правило 04).

    python tests/all_test.py

Каждый новый набор регистрируется в списке `SUITES`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_data import DataTests  # noqa: E402
from tests.test_homework import HomeworkRegistryTests  # noqa: E402
from tests.test_hw00 import Hw00Tests  # noqa: E402
from tests.test_metrics import MetricsTests  # noqa: E402
from tests.test_models import ModelsTests  # noqa: E402

SUITES = [MetricsTests, ModelsTests, DataTests, HomeworkRegistryTests, Hw00Tests]


def main() -> int:
    all_green = True
    for cls in SUITES:
        all_green &= cls().run_all()
    print("\n" + ("🎉 ВСЁ ЗЕЛЁНОЕ" if all_green else "❌ ЕСТЬ ПАДЕНИЯ"))
    return 0 if all_green else 1


if __name__ == "__main__":
    raise SystemExit(main())
