# hw01 · результаты прогонов (отобранные артефакты)

> Здесь лежит то, что стоит показать: отчёты реальных прогонов сканера, метрики ДЗ и расход токенов.
> Полный `out/hw01/` (логи по 7 МБ, сгенерированные деревья, замеры) в git не идёт — он воспроизводится
> командами ниже. Все файлы — как их выдал сканер, без правок руками.

| Файл | Что это | Как получено |
|---|---|---|
| `metrics.json` | метрики ДЗ: счётчики набора A, `extract_f1`, `classify_accuracy`, `speedup`, длительности | `python run_hw.py hw01` |
| `reference_tree_report.md` | отчёт сканера по эталонному дереву (набор A: 28 файлов, 82 ссылки, ровно 7 битых) | часть `run_hw.py hw01` (`out/hw01/reference/`) |
| `dsp-gpu_org_report.md` | **боевой прогон по организации** `dsp-gpu`: 10 приватных репозиториев, клон `--depth 1`, HTTP включён | `python -m core.mdscan https://github.com/dsp-gpu -source.auth:ssh` (69.5 с; секция «HTTP 401/403/429» — бот-защита научных сайтов; часть `github.com/…/issues/N` в этот раз ответила 404 — так ответил сервер, проверять вручную) |
| `dsp-gpu_local_report.md` | прогон по **локальному** репозиторию DSP-GPU с сетью (846 файлов, 1063 ссылки, `.gitignore` учтён) | `python -m core.mdscan <путь к DSP-GPU>` (этап 2, H-02, прогон b) |
| `http_live_report.md` + `http_live_links.md.txt` | живые HTTP-исходы: `OK` / `BROKEN` (404, DNS) / `TIMEOUT` разведены, коды у битых, кэш по URL | `python -m core.mdscan out/hw01/h03 -scan.respect_gitignore:false` на файле `links.md` (здесь — `http_live_links.md.txt`, чтобы его нарочно битые ссылки не попадали в чужие сканы) (этап 2, H-03) |
| `console_example.txt` | как выглядит консольная сводка (rich-таблица итогов и битых) | stdout прогона DSP-GPU без сети |
| `tokens_stage1.md` | расход токенов этапа 1 (разработка T-01…T-16, 17 запусков агентов) | `python -m core.tokenstat --since out/hw01/build_start.txt` |
| `tokens_stage2.md` | расход токенов этапа 2 (боевая приёмка H-01…H-13, 14 запусков) — по таскам, агенты/оркестрант | `python -m core.tokenstat --since out/hw01/build_start_stage2.txt` |

Настройки — `../mdscan.example.yaml` (все поля с комментариями; такой же файл сканер создаёт сам
при первом запуске в каталоге запуска). Описание каждого параметра, закон CLI, коды возврата —
`Doc/Modules/mdscan/CLI.md`; архитектура и производительность — `Doc/Modules/mdscan/README.md`;
подробные протоколы этапа 2 (числа по каждому таску) — `MemoryBank/specs/hw01_h*_2026-08-17.md`.

## Как воспроизвести

```bash
pip install -e .[hw01,dev]                                   # зависимости
python run_hw.py hw01                                        # метрики ДЗ → out/hw01/metrics.json
python -m core.mdscan <каталог|URL репо|URL организации|yaml> [-поле:значение …]
python -m core.mdscan out/hw01/fixture_tree -scan.respect_gitignore:false -http.enabled:false   # эталонное дерево
python tests/hw01/support/bench_scan.py --workers 1 --repeat 5 --layers   # замер по слоям
python -m pytest tests/hw01 -q                               # 444 тестов; живая сеть: MDSCAN_NETWORK=1 pytest -m network
```
