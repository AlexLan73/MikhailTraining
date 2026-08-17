# H-03 — живые HTTP-исходы

Набор ссылок для боевой проверки `HttpChecker` (таск H-03). Каждая строка — свой ожидаемый исход.

## 1. Живой сайт с быстрым ответом (ожидается OK)

- [example.com](https://example.com/)
- [python.org](https://www.python.org/)

## 2. Та же ссылка второй раз — проверка кэша (один сетевой запрос на URL)

- [example.com ещё раз](https://example.com/)
- [python.org ещё раз](https://www.python.org/)

## 3. Страница, которой нет на живом домене (ожидается BROKEN + код 404)

- [нет такого репозитория на GitHub](https://github.com/AlexLan73/no-such-repo-xyz-h03)
- [httpbin 404](https://httpbin.org/status/404)

## 4. Домен, которого не существует (ожидается BROKEN, код 0, ошибка DNS)

- [несуществующий домен](https://no-such-domain-mdscan-h03-2026.invalid/)

## 5. Адрес, который не отвечает (ожидается TIMEOUT)

- [чёрная дыра 10.255.255.1](http://10.255.255.1/)
- [httpbin задержка 10 с](https://httpbin.org/delay/10)

## 6. Ссылка на GitHub — категория GITHUB, а не URL

- [профиль AlexLan73](https://github.com/AlexLan73)
- [gist.github.com](https://gist.github.com/)

## 7. Редирект 301 (http -> https, ожидается OK после перехода)

- [http://github.com](http://github.com/)
- [http://www.python.org](http://www.python.org/)

## 8. Локальные ссылки — контроль, что HTTP не смешивается с локальной проверкой

- [этот же файл](links.md)
- [файла нет](no-such-file-h03.md)
