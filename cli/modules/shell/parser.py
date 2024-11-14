from modules.shell import commands
from modules.tui import style

from collections.abc import Callable
import shlex


def find_command(name: str) -> commands.Command | None:
    for cmd in commands.commands_register:
        if name == cmd.name or name in cmd.aliases:
            return cmd


def parse_query(raw_query: str, shell) -> list[commands.Command, Callable]:
    """
    Parse user input to callable command. Returns Command and ready-to-call lambda or
    raises ValueError with a displayable error message.
    """
    parts = shlex.split(raw_query)
    if not parts:
        raise ValueError("Blank input.")

    command_name = parts[0]
    command = find_command(command_name)
    if command is None:
        raise ValueError(f"Command: {style.Fore.RED}`{command_name}`{style.RESET} not found.")

    query_params = parts[1:]

    if len(query_params) > len(command.params):
        raise ValueError(f"Too many parameters ({style.Fore.RED}{len(query_params)}{style.RESET}) for command that requires at most {style.Fore.RED}{len(command.params)}{style.RESET} parameters.")

    res_params = {}
    for index, param in enumerate(command.params):
        param_t = param.type.value

        try:
            q_value = query_params[index]
        except IndexError:
            if param.default is None:
                raise ValueError(f"Missing parameter {style.Fore.RED}{index + 1}{style.RESET} {param}")
            res_params[param.name] = param.default
            continue
        
        if not param_t.validator(q_value):
            raise ValueError(f"Invalid value {style.Fore.RED}`{q_value}`{style.RESET} for parameter of type: {style.Fore.RED}{param_t.name}{style.RESET}")

        res_value = param_t.factory(q_value)
        res_params[param.name] = res_value
        
    return [command, lambda: command.call(shell, res_params)]
