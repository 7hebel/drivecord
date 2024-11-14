from modules.tui import style
from modules import fs

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from modules.shell.shell import ShellSession


def get_usage(shell: "ShellSession", params: dict[str, Any]) -> None:
    shell.instance.debug_api.get_memory_usage()
    
    
def dump_cache(shell: "ShellSession", params: dict[str, Any]) -> None:
    index = params.get("BucketIndex")
    shell.instance.debug_api.dump_cache(index)
    
    
def recache(shell: "ShellSession", params: dict[str, Any]) -> None:
    index = params.get("BucketIndex")
    shell.instance.debug_api.recache(index)
    
    
def trace_file(shell: "ShellSession", params: dict[str, Any]) -> None:
    path = params.get("Path")
    file = shell.cwd.move_to(path)
    
    if not file:
        return print(style.error_msg("Invalid path."))
    
    if isinstance(file, fs.FS_Dir):
        return print(style.error_msg("Object is a directory, file expected."))
    
    shell.instance.debug_api.trace_file(file.path_to)
    
    