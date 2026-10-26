# Лабораторная работа № 2. Потоковый анализатор журналов

Программа `streamstats` читает журнал событий в формате CSV или JSON Lines, проверяет записи и считает статистику. Файл обрабатывается построчно и целиком в память не загружается.

Отчёт содержит число событий, распределение по уровням и источникам, источники с наибольшим числом ошибок, время первой и последней записи и число пропущенных строк. Результат записывается в JSON. Те же итоги можно дополнительно сохранить в CSV без повторного чтения журнала.

## Структура проекта

```text
lab-02/
├── README.md
├── pyproject.toml
├── src/
│   └── streamstats/
│       ├── __init__.py
│       ├── __main__.py
│       ├── analysis.py
│       ├── cli.py
│       ├── constants.py
│       ├── errors.py
│       ├── filters.py
│       ├── logging_setup.py
│       ├── main.py
│       ├── models.py
│       ├── parsers.py
│       └── report.py
└── tests/
    ├── test_analysis.py
    ├── test_cli.py
    ├── test_parsers.py
    └── test_report.py
```

`parsers.py` разбирает строки входного файла. `analysis.py` проверяет записи и накапливает статистику. `report.py` собирает отчёт и записывает JSON и CSV. `cli.py` принимает аргументы командной строки. `logging_setup.py` настраивает журнал работы самой программы. `__main__.py` позволяет запускать пакет командой `python -m streamstats`.

## Требования

Python 3.12 или новее.

## Установка

Команды выполняются в корне проекта, в каталоге `lab-02`.

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install pytest
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install pytest
```

### Windows

В PowerShell или в командной строке:

```powershell
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install -e .
python -m pip install pytest
```

Если команда `py` недоступна, вместо неё используется `python`. Если PowerShell блокирует активацию, те же команды выполняются в cmd.

При успешном включении окружения в начале строки появляется `(.venv)`. Дальнейшие команды запуска одинаковы для macOS, Linux и Windows.


## Формат входных данных

Обязательные поля записи: `timestamp`, `level`, `source`, `message`. Время задаётся в формате ISO 8601 и содержит часовой пояс.

В CSV имена полей находятся в первой строке. Пример `data/events.csv`:

```csv
timestamp,level,source,message
2026-10-07T12:00:00+03:00,INFO,loader,Начало чтения файла
2026-10-07T09:10:00+00:00,ERROR,db,Нет соединения с базой
2026-10-07T09:20:00Z,CRITICAL,db,База недоступна
```

В JSON Lines каждая строка файла является отдельным JSON-объектом:

```json
{"timestamp": "2026-10-07T09:10:00+00:00", "level": "ERROR", "source": "db", "message": "Нет соединения с базой"}
```

## Использование

Справка:

```bash
python -m streamstats --help
python -m streamstats analyze --help
```

Отчёт в JSON:

```bash
python -m streamstats analyze data/events.csv --format csv --output report.json
```

JSON и CSV из одного прохода по журналу:

```bash
python -m streamstats analyze data/events.csv --format csv --output report.json --csv-output report.csv
```

Журнал в формате JSON Lines:

```bash
python -m streamstats analyze data/events.jsonl --format jsonl --output report.json
```

Несколько файлов одного формата указываются подряд:

```bash
python -m streamstats analyze data/one.csv data/two.csv --format csv --output report.json
```

Параметр `--output` обязателен: по этому пути всегда создаётся JSON-отчёт. Файл CSV создаётся только при наличии `--csv-output`. При ошибке во входных данных или аргументах программа сообщает причину и завершается с кодом 2.

## Параметры

| Параметр | Назначение |
| --- | --- |
| `--format csv` или `--format jsonl` | Формат входных файлов |
| `--output report.json` | Путь к JSON-отчёту |
| `--csv-output report.csv` | Дополнительный CSV с теми же итогами |
| `--skip-invalid` | Пропускать повреждённые строки вместо остановки |
| `--level ERROR` | Оставить события только этого уровня |
| `--source db` | Оставить события только этого источника |
| `--since 2026-10-07T09:00:00+00:00` | Оставить события не раньше указанного времени |
| `--until 2026-10-07T12:00:00+00:00` | Оставить события не позже указанного времени |
| `--log run.log` | Записать ход работы программы в указанный файл |

## Тестирование

```bash
pytest
```
