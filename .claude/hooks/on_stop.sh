#!/usr/bin/env bash
# Hook: Stop — напоминание обновить MemoryBank в конце сессии

TODAY="$(date +%Y-%m-%d)"
SESSION_FILE="MemoryBank/sessions/${TODAY}.md"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 [HOOK] Сессия завершена — ${TODAY}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Если что-то важное сделали:"
echo "   1. Создай/обнови: ${SESSION_FILE}"
echo "   2. Обнови: MemoryBank/MASTER_INDEX.md (статус ДЗ)"
echo "   3. Сданные ДЗ → отметь ✅ в MemoryBank/tasks/"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

exit 0
