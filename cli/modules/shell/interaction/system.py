from modules.tui import style, list_view
from modules import api, storage

from typing import Any, TYPE_CHECKING
import sys

if TYPE_CHECKING:
    from modules.shell.shell import ShellSession


def _logout():
    api.AccessAPI.logout()
    storage.reset_all()
    

def help_command(shell: "ShellSession", params: dict[str, Any]) -> None:
    cmd_name = params.get("CmdName")
    
    if cmd_name:
        for cmd in shell._cmds_register:
            if cmd_name == cmd.name or cmd_name in cmd.aliases:
                break
        else:
            raise ValueError(f"Cannot display documentation for: {style.Fore.RED}`{cmd_name}`{style.RESET} (command not found)")
    
        print(cmd.help_full())
        return
    
    listview = list_view.ListView("List of commands.")
    
    for group in shell._cmds_groups:
        listview.group(group.value)
        
        for command in shell._cmds_register:
            if command.group == group:
                listview.item(command.help_inline())       
    
        
    listview.finish()
    

def exit_command(shell: "ShellSession", params: dict[str, Any]) -> None:
    with_logout = params.get("Logout")
    
    if with_logout:
        _logout()
        
    sys.exit(0)


def logout_command(shell: "ShellSession", params: dict[str, Any]) -> None:
    _logout()
    sys.exit(0)


def switch_instance_command(shell: "ShellSession", _) -> None:
    shell.select_instance()
