# Окружение проекта MikhailTraining

> Инструменты, которые нужны для запуска ДЗ и утилит репозитория.
> Обновляется при каждой установке нового инструмента (правило: помечать в доках обязательно).

---

## 1. GitHub CLI (`gh`) — установлен 2026-08-16

### Зачем нужен

Получить **список репозиториев организации** (например `dsp-gpu`) можно только через GitHub API.
По SSH git умеет работать лишь с конкретным репозиторием, чей адрес уже известен.
`gh` даёт авторизованный доступ к API без ручного хранения токенов в файлах проекта.

Используется в hw01 (`GitHubOrgSource`) — см. `MemoryBank/specs/hw01_mdscan_reasoning_2026-08-16.md`, D3.3.

### Как установлен (Windows, без прав администратора)

`winget`, `scoop`, `choco` в системе отсутствуют, поэтому поставлена **portable-версия**:

| Параметр | Значение |
|---|---|
| Версия | `gh 2.97.0` (2026-07-31) |
| Источник | `https://github.com/cli/cli/releases/download/v2.97.0/gh_2.97.0_windows_amd64.zip` (14.2 МБ) |
| Каталог | `%USERPROFILE%\.local\gh\` (бинарник — `...\.local\gh\bin\gh.exe`) |
| PATH | `%USERPROFILE%\.local\gh\bin` добавлен в **пользовательский** PATH |

Проверка: `gh --version` → `gh version 2.97.0`.

⚠️ Новый PATH подхватывается **новыми** оболочками. В уже открытом терминале:
`$env:Path += ";$env:USERPROFILE\.local\gh\bin"`.

### Авторизация (делает Alex, один раз)

Команда интерактивная, её нельзя выполнить из-под ассистента:

```bash
gh auth login
```

Выбрать: `GitHub.com` → `SSH` (ключ уже настроен и работает) → авторизация через браузер.

Проверка после входа:

```bash
gh auth status
gh repo list dsp-gpu --limit 100          # список репозиториев организации
```

**Текущее состояние**: ✅ `gh` установлен и **авторизован** — `Logged in as AlexLan73`
(GitHub.com, протокол HTTPS, вход через браузер, 2026-08-16).

Проверено сразу после входа:

```bash
gh repo list dsp-gpu --limit 100 --json name,sshUrl,isPrivate
```

Вернул **10 приватных репозиториев** организации: `workspace`, `heterodyne`, `DSP`, `radar`,
`signal_generators`, `core`, `spectrum`, `strategies`, `linalg`, `stats`.

⚠️ В PowerShell вызывать через оператор `&` и в кавычках, иначе парсер ругается:

```powershell
& "$env:USERPROFILE\.local\gh\bin\gh.exe" repo list dsp-gpu --limit 100
```

### Обновление

```bash
gh --version
# скачать новый zip из releases и распаковать в тот же каталог с -Force
```

### Debian (рабочая машина)

```bash
sudo apt install gh          # или см. https://github.com/cli/cli/blob/trunk/docs/install_linux.md
gh auth login
```

---

## 2. Git и доступ к GitHub

| Что | Состояние (проверено 2026-08-16) |
|---|---|
| `git` | `C:\Program Files\Git\cmd\git.exe` |
| SSH-ключ | ✅ работает: `ssh -T git@github.com` → `Hi AlexLan73!` |
| Личный репозиторий | ✅ `git ls-remote git@github.com:AlexLan73/GPUWorkLib.git` |
| Приватный репозиторий организации | ✅ `git ls-remote git@github.com:dsp-gpu/radar.git` |
| Список репозиториев организации | ✅ работает через `gh repo list dsp-gpu` (после `gh auth login`) |

### GitHub MCP-сервер

Настроен в `C:\Users\user\.claude.json` (`mcpServers.github`), переменная
`GITHUB_PERSONAL_ACCESS_TOKEN` задана, но вызовы возвращают `Bad credentials` —
**токен истёк или отозван**. Варианты:

1. обновить токен в `.claude.json` (права: `repo`, `read:org`), перезапустить Claude Code;
2. либо пользоваться `gh` после `gh auth login` — тогда MCP не нужен.

---

## 3. Python

| Что | Значение |
|---|---|
| Интерпретатор | `.venv\Scripts\python.exe` в корне репозитория |
| Версия | ≥ 3.11 |
| Тесты | `pytest` (стандарт проекта с 2026-08-16), legacy-наборы — `python tests/all_test.py` |
| Установлено дополнительно | `pytest 9.1.1`, `pytest-cov 7.1.0` |
| Не установлено (нужно для линта) | `ruff`, `mypy` → `pip install -e .[dev]` |

### Зависимости, запланированные для hw01

| Пакет | Зачем | Статус |
|---|---|---|
| `markdown-it-py` | разбор Markdown и извлечение ссылок (D7) | не установлен |
| `mdit-py-plugins` | плагины синтаксиса (footnote и др., D7.1) | не установлен |
| `GitPython` | корень репозитория, submodules, `ls-files`, `clone --depth 1` (D7.4) | не установлен |
| `PyYAML` | чтение/создание `mdscan.yaml` (D19) | не установлен |
| `rich` | цветная консоль (опционально, есть fallback) | не установлен |

---

*Создан 2026-08-16. Ведёт: Кодо. Дополнять при каждой установке инструмента.*
