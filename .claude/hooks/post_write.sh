#!/usr/bin/env bash
# Hook: PostToolUse(Write|Edit) — напоминания при изменении ключевых файлов MikhailTraining

RAW="$(cat)"
PY="python3"
command -v python3 >/dev/null 2>&1 || PY="python"
FILE_PATH="$(echo "${RAW}" | "${PY}" -c "import json,sys; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))" 2>/dev/null || echo "")"

if [[ -z "${FILE_PATH}" ]]; then
    exit 0
fi

# CLAUDE.md изменён
if [[ "${FILE_PATH}" =~ CLAUDE\.md$ ]]; then
    echo ""
    echo "📝 [HOOK] CLAUDE.md изменён → проверь MemoryBank/MASTER_INDEX.md если поменялась структура"
fi

# Новое/изменённое ДЗ — напоминание про реестр и README
if [[ "${FILE_PATH}" =~ homework/hw[0-9]+_.+\.py$ ]]; then
    echo ""
    echo "🎓 [HOOK] Изменено ДЗ: $(basename "${FILE_PATH}")"
    echo "   → зарегистрировано в homework/registry.py? (иначе run_hw.py --list не увидит)"
    echo "   → README.md ДЗ: условие / что сделано / метрики / выводы"
    echo "   → прогони: pytest (+ python tests/all_test.py для legacy-наборов)"
fi

# Изменён общий код core — тесты обязательны
if [[ "${FILE_PATH}" =~ core/.+\.py$ ]]; then
    echo ""
    echo "🧪 [HOOK] Изменён core-код: $(basename "${FILE_PATH}")"
    echo "   → прогони: pytest (+ python tests/all_test.py для legacy-наборов)"
    echo "   → метрику/формулу сверь с эталоном (numpy/sklearn)"
fi

# Публичный API — обновить README
if [[ "${FILE_PATH}" =~ core/.+/__init__\.py$ ]]; then
    echo ""
    echo "📋 [HOOK] Изменён __init__ (публичный API) → обнови README.md при смене интерфейса"
fi

# Заглавная папка Core — частая ошибка
if [[ "${FILE_PATH}" =~ /Core/ ]]; then
    echo ""
    echo "⚠️  [HOOK] Путь содержит 'Core/' — пакет должен быть строчным 'core/' (Linux ФС регистрозависима)!"
fi

exit 0
