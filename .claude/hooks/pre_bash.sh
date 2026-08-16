#!/usr/bin/env bash
# Hook: PreToolUse(Bash) — защита от опасных команд (Windows Git Bash / Debian)
# exit 2 = заблокировать команду

RAW="$(cat)"
PY="python3"
command -v python3 >/dev/null 2>&1 || PY="python"
CMD="$(echo "${RAW}" | "${PY}" -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")"

if [[ -z "${CMD}" ]]; then
    exit 0
fi

# Опасные паттерны
DANGEROUS=(
    "git reset --hard"
    "git clean -f"
    "git push --force"
    "git push -f "
    "git branch -D"
    "rm -rf /"
    "rm -rf ~"
    "rm -rf \$HOME"
)

for pat in "${DANGEROUS[@]}"; do
    if [[ "${CMD}" == *"${pat}"* ]]; then
        echo ""
        echo "⛔ [HOOK] ЗАБЛОКИРОВАНО: обнаружена опасная операция!"
        echo "   Команда содержит: '${pat}'"
        echo "   Подтверди явно в чате, если уверен."
        exit 2
    fi
done

# pytest РАЗРЕШЁН с 2026-08-16 — стандарт тестирования проекта
# (см. .claude/rules/04-testing-python.md). Блокировка снята намеренно.

exit 0
