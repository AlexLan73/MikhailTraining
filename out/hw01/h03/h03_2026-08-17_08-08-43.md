# Отчёт mdscan — h03

## Прогон

| параметр | значение |
| --- | --- |
| старт | 2026-08-17 08:08:43 |
| длительность, с | 21.69 |
| код возврата | 1 |

## Цель

| цель | вид |
| --- | --- |
| `E:\MikhailTraining\out\hw01\h03` | local |

## Репозитории

| корень | web_url | вложенный |
| --- | --- | --- |
| `E:\MikhailTraining` | `https://github.com/AlexLan73/MikhailTraining` | нет |

## Статистика по типам ссылок

| категория | всего | ok | broken | timeout | skipped |
| --- | --- | --- | --- | --- | --- |
| local | 2 | 1 | 1 | 0 | 0 |
| github | 4 | 3 | 1 | 0 | 0 |
| url | 9 | 5 | 1 | 3 | 0 |

### Счётчики прогона

| счётчик | значение |
| --- | --- |
| broken_anchor | 0 |
| broken_http | 2 |
| broken_local | 1 |
| broken_ratio | 0.400 |
| broken_total | 6 |
| duration_sec | 21.687 |
| error_rate | 0 |
| files_failed | 0 |
| files_ok | 1 |
| links_anchor | 0 |
| links_footnote | 0 |
| links_github | 4 |
| links_local | 2 |
| links_mailto | 0 |
| links_tel | 0 |
| links_total | 15 |
| links_unknown | 0 |
| links_url | 9 |
| links_wikilink | 0 |
| md_files_total | 1 |
| repos_nested | 0 |
| repos_total | 1 |
| throughput_files_per_sec | 0.046 |
| timeout_http | 3 |

## Файлы

| репозиторий | путь | ссылок | статус | ошибка |
| --- | --- | --- | --- | --- |
| `MikhailTraining` | `out/hw01/h03/links.md` | 15 | битых: 6 | — |

## Битые локальные ссылки

| файл | строка | цель | причина |
| --- | --- | --- | --- |
| `MikhailTraining/out/hw01/h03/links.md` | 42 | `no-such-file-h03.md` | нет файла: no-such-file-h03.md |

## Битые HTTP-ссылки

| файл | строка | url | код | причина |
| --- | --- | --- | --- | --- |
| `MikhailTraining/out/hw01/h03/links.md` | 17 | `https://github.com/AlexLan73/no-such-repo-xyz-h03` | 404 | HTTP 404 |
| `MikhailTraining/out/hw01/h03/links.md` | 22 | `https://no-such-domain-mdscan-h03-2026.invalid/` | — | адрес недоступен: [Errno 11001] getaddrinfo failed |

## HTTP 401/403/429 — вероятно защита от ботов или лимит (проверить вручную)

_нет_

## Таймауты

| файл | строка | цель | категория |
| --- | --- | --- | --- |
| `MikhailTraining/out/hw01/h03/links.md` | 18 | `https://httpbin.org/status/404` | url |
| `MikhailTraining/out/hw01/h03/links.md` | 26 | `http://10.255.255.1/` | url |
| `MikhailTraining/out/hw01/h03/links.md` | 27 | `https://httpbin.org/delay/10` | url |

## Файлы с ошибками

_нет_

