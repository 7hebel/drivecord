from modules.paths import Path
from modules import timestamp

from colorama import Fore, Back, init
import logging.handlers
import traceback
import logging
import inspect
import os


init(autoreset=True)
LOGS_PATH = Path("./logs/")
TRACEBACK_LOG_PATH = LOGS_PATH + "traceback.log"


def get_time() -> str:
    """ Returns current date and time in format: DD/MM/YYYY HH:MM:SS """
    now = timestamp.Datetime.now()
    return f"{now.day:02d}/{now.month:02d}/{now.year} {now.hour:02d}:{now.minute:02d}:{now.second:02d}"


def _get_current_logs_filepath() -> Path:
    """ Get time-based log file path. """
    now = timestamp.Datetime.now()
    return LOGS_PATH + f"{now.year}_{now.month:02d}_{now.day:02d}.log"


def _save_log(content: str) -> None:
    """ Write content to current logs file. """
    fp = _get_current_logs_filepath()
    fp.write(content + "\n", "a+")


def _get_caller_info():
    """ Get information about place in code where log method was called. """
    caller_frame = inspect.stack()[2]
    filename = os.path.basename(caller_frame.filename)
    function = caller_frame.function
    lineno = caller_frame.lineno
    if function == "<module>":
        function = "@"
    return f"{filename}:{function}#{lineno}"


def _save_traceback_log(traceback: list[str]) -> None:
    """ Save traceback to errors log file. """
    header = f"--- TRACEBACK: ({get_time()}) ---\n\n"
    content = header + "".join(traceback) + "\n\n\n"
    TRACEBACK_LOG_PATH.write(content, "a+")


class Log:

    @staticmethod
    def _log(level: int, message: str, caller: str) -> None:
        now = timestamp.Datetime.now()
        time = f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}"

        if level == 0:
            print(f"{Fore.WHITE}{time} {Fore.LIGHTBLACK_EX}| {Fore.BLUE}info {Fore.LIGHTBLACK_EX}| {Fore.WHITE}{message} {Fore.LIGHTBLACK_EX}({caller})")
            _save_log(f"{time} | info | {message} ({caller})")

        if level == 1:
            print(f"{Fore.WHITE}{time} {Fore.LIGHTBLACK_EX}| {Fore.YELLOW}warn {Fore.LIGHTBLACK_EX}| {Fore.LIGHTYELLOW_EX}{message} {Fore.LIGHTBLACK_EX}({caller})")
            _save_log(f"{time} | warn | {message} ({caller})")

        if level == 2:
            print(f"{Fore.WHITE}{time} {Fore.LIGHTBLACK_EX}| {Back.RED}{Fore.WHITE}ERROR{Back.RESET}{Fore.LIGHTBLACK_EX}| {Fore.RED}{message} {Fore.LIGHTBLACK_EX}({caller})")
            _save_log(f"{time} | ERROR| {message} ({caller})")

    @staticmethod
    def info(message: str) -> None:
        """ Save log with `info` level and print content. """
        Log._log(0, message, _get_caller_info())

    @staticmethod
    def warn(message: str) -> None:
        """ Save log with `warn` level and print content. """
        Log._log(1, message, _get_caller_info())

    @staticmethod
    def error(message: str) -> None:
        """ Save log with `error` level and print content. """
        Log._log(2, message, _get_caller_info())


class _DCLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level_formats = {
            logging.INFO: f" {Fore.BLUE}info ",
            logging.WARNING: f" {Fore.YELLOW}warn ",
            logging.ERROR: f" {Back.RED}{Fore.WHITE}ERROR{Back.RESET}",
            logging.CRITICAL: f" {Back.RED}{Fore.YELLOW}CRIT{Back.RESET} "
        }

        content_formats = {
            logging.INFO: f"{Fore.WHITE}{record.getMessage()}",
            logging.WARNING: f"{Fore.YELLOW}{record.getMessage()}",
            logging.ERROR: f"{Fore.RED}{record.getMessage()}",
            logging.CRITICAL: f"{Back.RED}{Fore.YELLOW}{record.getMessage()}{Back.RESET}"
        }

        now = timestamp.Datetime.now()
        time = f"{now.hour:02d}:{now.minute:02d}:{now.second:02d}"

        content = f"{Fore.WHITE}{time} {Fore.LIGHTBLACK_EX}|{level_formats.get(record.levelno)}{Fore.LIGHTBLACK_EX}| {content_formats.get(record.levelno)} {Fore.MAGENTA}({record.name})"

        if record.exc_info:
            err_type, error_content, tb = record.exc_info
            error_name = err_type.__name__
            tb_content = traceback.format_exception(*record.exc_info)
            _save_traceback_log(tb_content)

            content += f"\n                  {Fore.WHITE}<{error_name}> {Fore.RED}{error_content}"

        return content
