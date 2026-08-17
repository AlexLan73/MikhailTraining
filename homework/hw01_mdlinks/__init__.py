"""ДЗ 01 — «Markdown / Git Scanner»: сканер ссылок в Markdown (фасад пакета).

Наружу торчит только класс задания; генератор деревьев остаётся в
`homework.hw01_mdlinks.support` и импортируется оттуда напрямую (его зовут и pytest,
и сам прогон ДЗ).
"""

from .task import Hw01MdLinks

__all__ = ["Hw01MdLinks"]
