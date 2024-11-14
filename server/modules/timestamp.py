"""
Module: timestamp.py

Description:
    Simple POSIX timestamp generator and parser.
"""
from datetime import datetime as Datetime
from datetime import timedelta
from functools import lru_cache


def generate_timestamp(datetime: Datetime | None = None) -> int:
    """
    Generate timestamp. If datetime param is not provided, current datetime will be used.
    """
    if datetime is None:
        return int(Datetime.now().timestamp())
    return int(datetime.timestamp())


@lru_cache
def read_timestamp(timestamp: int) -> Datetime:
    """ Read POSIX timestamp. """
    return Datetime.fromtimestamp(timestamp)


@lru_cache
def convert_to_readable(timestamp: int) -> str:
    """ Convert timestamp into string with date and time in readable form. """
    dt = read_timestamp(timestamp)
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year} {dt.hour:02d}:{dt.minute:02d}"


@lru_cache
def timestamp_to_page_displayable(timestamp: int) -> str:
    dt = read_timestamp(timestamp)
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year}"


@lru_cache
def convert_to_timestamp(readable: str) -> int:
    """ Convert date in format made by convert_to_readable() back to timestamp. """
    date_format = "%d/%m/%Y %H:%M"
    parsed_datetime = Datetime.strptime(readable, date_format)
    posix_timestamp = parsed_datetime.timestamp()
    return int(posix_timestamp)


def add_minutes_to_timestamp(minutes: int, timestamp: int) -> int:
    """ Returns new timestamp. """
    dt = read_timestamp(timestamp)
    return generate_timestamp(dt + timedelta(minutes=minutes))
