from modules.tui import style, tree_view, file
from modules import downloads
from modules import fs

from typing import Any, TYPE_CHECKING
from click import edit
import base64
import os

if TYPE_CHECKING:
    from modules.shell.shell import ShellSession


def list_dir(shell: "ShellSession", params: dict[str, Any]) -> None:
    recursive = params.get("Recursive")
    
    struct = shell.instance.fs_api.get_struct()
    base = fs.load_structure(struct)
    target = base.move_to(shell.cwd.path_to)

    if target is None:
        print(style.error_msg("Your current working directory seems to be corrupted."))
        target = base
        shell.cwd = base

    if base is None:
        return print(style.error_msg("Failed to display structure content."))
    
    treeview = tree_view.TreeView(target, recursive)
    treeview.draw()
    treeview.finish()
    
    
def make_file(shell: "ShellSession", params: dict[str, Any]) -> None:
    path = params.get("Path")
    shell.instance.fs_api.make_file(path)
    
    
def make_dir(shell: "ShellSession", params: dict[str, Any]) -> None:
    path = params.get("Path")
    shell.instance.fs_api.make_dir(path)    
    
    
def change_directory(shell: "ShellSession", params: dict[str, Any]) -> None:
    shell.update_struct()
    
    path = params.get("Path")
    target = shell.cwd.move_to(path)

    if target is None:
        return print(style.error_msg(f"Target path doesn't exist: {shell.cwd.path_to}{path}"))

    if isinstance(target, fs.FS_File):
        return print(style.error_msg(f"Selected object: {path} is a file."))
    
    shell.cwd = target
    
    
def cd_home(shell: "ShellSession", params: dict[str, Any]) -> None:
    return change_directory(shell, {"Path": "~"})
    
    
def remove_object(shell: "ShellSession", params: dict[str, Any]) -> None:
    shell.instance.fs_api.remove_object(params.get("Path"))
    

def rename_object(shell: "ShellSession", params: dict[str, Any]) -> None:
    shell.instance.fs_api.rename_object(params.get("Path"), params.get("NewName"))
    

def read_file(shell: "ShellSession", params: dict[str, Any]) -> None:
    path = params.get("Path")
    content = shell.instance.fs_api.read_file(path)
    
    if isinstance(content, str):
        file.display_content(os.path.basename(path), content)
    

def pull_object(shell: "ShellSession", params: dict[str, Any]) -> None:
    path = params.get("Path")
    override = params.get("Override")

    data = shell.instance.fs_api.pull_object(path)
    if not data:
        return print(style.error_msg("Failed to pull object."))
    
    downloads.handle_pulled_data(shell.instance.name, data, override)
    

def edit_file(shell: "ShellSession", params: dict[str, Any]) -> None:
    path = params.get("Path")

    content = shell.instance.fs_api.read_file(path)
    if not content:
        return print(style.error_msg("Failed to fetch current content."))
    
    edited_content = edit(content)
    if edited_content is None:
        return print(style.error_msg("Edit operation manually canceled."))
    
    shell.instance.fs_api.write_file(path, edited_content)


def upload_file(shell: "ShellSession", params: dict[str, Any]) -> None:
    local_path = params.get("LocalPath")
    filename = os.path.basename(local_path)
    path = shell.cwd.path_to + filename
    
    if not os.path.exists(local_path):
        return print(style.error_msg(f"Local file not found: {local_path}"))

    with open(local_path, "rb") as file:
        content = base64.b64encode(file.read()).decode()
    
    shell.instance.fs_api.upload_file(path, content)
    