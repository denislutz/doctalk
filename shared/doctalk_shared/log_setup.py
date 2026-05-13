import json
import logging
import logging.handlers
import pathlib


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "ts": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "msg": record.getMessage(),
            }
        )


_configured: set[str] = set()


def setup_logging(
    log_filename: str,
    *,
    level: int = logging.DEBUG,
    log_dir: pathlib.Path,
) -> None:
    if log_filename in _configured:
        return
    _configured.add(log_filename)

    log_dir.mkdir(exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / log_filename, maxBytes=5_000_000, backupCount=3
    )
    file_handler.setFormatter(_JsonFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)

    for _noisy in ("httpcore", "httpx", "python_multipart"):
        logging.getLogger(_noisy).setLevel(logging.WARNING)
