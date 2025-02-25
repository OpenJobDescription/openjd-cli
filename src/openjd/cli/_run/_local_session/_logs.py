# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from dataclasses import dataclass
from logging import Handler, LogRecord
from datetime import datetime, timezone
from enum import Enum


class LoggingTimestampFormat(str, Enum):
    """
    Different formats for the timestamp of each log entry
    """

    RELATIVE = "relative"
    LOCAL = "local"
    UTC = "utc"


@dataclass
class LogEntry:
    """
    Log information from a sample Session to return in a CLI result.
    """

    timestamp: str
    message: str

    def __str__(self) -> str:
        return f"{self.timestamp}\t{self.message}"


class LocalSessionLogHandler(Handler):
    """
    A custom Handler that formats and records logs in a dataclass.
    Used to print logs to `stdout` in real time while also storing
    them in memory.

    It prints a timestamp that is relative to the session start.
    """

    messages: list[LogEntry] = []
    _should_print: bool
    _session_start_timestamp: datetime
    _timestamp_format: LoggingTimestampFormat

    def __init__(
        self,
        should_print: bool,
        session_start_timestamp: datetime,
        timestamp_format: LoggingTimestampFormat,
    ):
        super(LocalSessionLogHandler, self).__init__()
        self._should_print = should_print
        self._session_start_timestamp = session_start_timestamp
        self._timestamp_format = timestamp_format

    def handle(self, record: LogRecord) -> bool:
        if self._timestamp_format == LoggingTimestampFormat.RELATIVE:
            timestamp = str(
                datetime.fromtimestamp(record.created, timezone.utc) - self._session_start_timestamp
            )
        elif self._timestamp_format == LoggingTimestampFormat.LOCAL:
            timestamp = str(
                datetime.fromtimestamp(record.created, timezone.utc).astimezone().isoformat()
            )
        else:
            timestamp = str(datetime.fromtimestamp(record.created, timezone.utc).isoformat())

        record.created = datetime.fromtimestamp(record.created, timezone.utc).timestamp()
        new_record = LogEntry(
            timestamp=timestamp,
            message=record.getMessage(),
        )
        self.messages.append(new_record)

        if self._should_print:
            print(new_record)

        # No filters are applied to the message, so always return True
        return True
