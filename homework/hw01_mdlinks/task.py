"""ДЗ 01 — «Markdown / Git Scanner»: прогон сканера и метрики для README.

Тонкий оркестрант (часть 2, §4): строит тестовые деревья (наборы A и B), зовёт фасад
`core.mdscan` и складывает числа в `HomeworkReport.metrics`. Ни разбора, ни проверок
ссылок здесь нет — всё это живёт в `core/mdscan/`, счёт метрик — в `solution.py`.

Запуск: `python run_hw.py hw01` → артефакты в `out/hw01/` (лог, отчёт, `metrics.json`).
"""

from __future__ import annotations

import logging

from homework.hw01_mdlinks.solution import Hw01Metrics
from homework.hw01_mdlinks.support.fixture_tree_builder import FixtureTreeBuilder

# базу берём из модуля-реестра, здесь — только контракт задания
from homework.registry import HomeworkContext, HomeworkTask

logger = logging.getLogger("homework.hw01")


class Hw01MdLinks(HomeworkTask):
    """Прогон сканера по эталонному (A) и генерируемому (B) деревьям."""

    hw_id = "hw01"
    title = "CLI: Markdown Link & Dead Code Checker"

    #: Размер набора B: 200–500 файлов (спека §3.4); тесты ставят меньше — прогон быстрее.
    gen_files: int = 500  # набор B: 200–500 (§9.3); на 200 накладные расходы потоков съедают выигрыш
    #: Сколько потоков разбора сравнивается с одним в замере `speedup` (§9.3).
    parse_workers: int = 10  # = workers.parse по умолчанию (ревью 6, Alex)

    def solve(self, ctx: HomeworkContext) -> dict[str, float]:
        builder = FixtureTreeBuilder()
        tree = builder.reference(ctx.out_dir / "fixture_tree")
        generated = builder.generated(ctx.out_dir / "gen_tree", self.gen_files, ctx.seed)
        logger.info("деревья готовы: набор A %s, набор B %s", tree.root, generated)

        metrics = Hw01Metrics(ctx.out_dir)
        summary = metrics.scan(tree.root, "reference", self.parse_workers)

        result: dict[str, float] = dict(summary.counters)
        result["exit_code"] = float(summary.exit_code)
        result.update(metrics.quality(tree))
        result.update(metrics.parallel(generated, self.parse_workers))
        return result
