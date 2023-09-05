# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import time
from dataclasses import dataclass
from logging import Handler, LogRecord


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
    """

    messages: list[LogEntry] = []
    _should_print: bool

    def __init__(self, should_print: bool):
        super(LocalSessionLogHandler, self).__init__()
        self._should_print = should_print

    def handle(self, record: LogRecord) -> bool:
        new_record = LogEntry(
            timestamp=time.asctime(time.localtime(record.created)),
            message=record.getMessage(),
        )
        self.messages.append(new_record)

        if self._should_print:
            print(new_record)

        # No filters are applied to the message, so always return True
        return True
