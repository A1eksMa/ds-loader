from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional, Tuple

# --- Входной файл источника --------------------------------------------------


@dataclass(frozen=True)
class SourceFile:
    """Разобранное имя файла `<source>_YYYY-MM-DD_HH-MM-SS_<micros>.json`."""
    filename: str        # исходное имя, как в директории
    source: str          # всё до первого "_"
    timestamp: str       # "YYYY-MM-DD_HH-MM-SS_<micros>" — как в имени
    seconds_part: str    # "YYYY-MM-DD_HH-MM-SS" (без микросекунд)
    micros: int          # дробная часть метки времени


# --- Конфигурация ----------------------------------------------------------


@dataclass(frozen=True)
class SourceConfig:
    """Переопределения на уровне отдельного источника."""
    # Команда доменной подготовки native-формата в колоночный JSON перед `ds load`.
    # Зарезервировано — на текущем этапе НЕ выполняется (см. docs/roadmap).
    prep_cmd: Optional[Tuple[str, ...]] = None


@dataclass(frozen=True)
class Config:
    update_dir: str                                   # обязательно: что мониторим
    db_path: str = "data.db"
    sources_dir: str = "sources"
    archive_dir: str = "archive"
    quarantine_dir: str = "quarantine"
    ledger_path: str = ".ds-loader/ledger.jsonl"
    poll_interval_seconds: float = 5.0
    stable_after_seconds: float = 2.0                 # файл считается дописанным,
    #                                                  если mtime старше этого порога
    filename_tz: str = "utc"                          # как трактовать метку в имени: "utc" | "local"
    ds_command: Tuple[str, ...] = ("ds",)             # как звать ядро (список argv-префикса)
    ds_pythonpath: Optional[str] = None               # PYTHONPATH для процесса ядра
    #   (заменяет унаследованный; нужно, когда ds запускается как `python -m src.cli.commands`
    #    из чекаута без pip и его `src` конфликтует с `src` загрузчика)
    stages: Tuple[str, ...] = ("ingest",)            # какие стадии гоняет раннер за тик
    # --- стадия publish (перестройка выгрузки для ds-webui) ---
    webui_data_dir: Optional[str] = None             # каталог data/ рядом с index.html ds-webui;
    #                                                  обязателен, если в stages есть "publish"
    webui_preset: Optional[str] = None               # пресет для `ds get --preset`; None → все источники
    publish_state_path: str = ".ds-loader/publish.json"  # отпечатки опубликованного (гейтинг перезаписи)
    sources: Mapping[str, SourceConfig] = field(default_factory=dict)


# --- Отчёты --------------------------------------------------------------


@dataclass(frozen=True)
class FileOutcome:
    filename: str
    source: str
    # loaded | already-loaded | skipped-unstable | skipped-name | quarantined | error
    status: str
    detail: str = ""


@dataclass(frozen=True)
class StageReport:
    """Единый конверт результата любой стадии раннера."""
    stage: str
    ok: bool
    changed: int                        # единиц работы выполнено (напр. загружено файлов)
    lines: Tuple[str, ...] = ()         # человекочитаемый лог
    outcomes: Tuple[FileOutcome, ...] = ()   # заполняет стадия ingest; прочие — пусто
