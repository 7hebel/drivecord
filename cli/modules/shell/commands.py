from modules.shell import interaction
from modules.tui import style
from modules import perms

from typing import Generic, TypeVar, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from collections.abc import Callable
from enum import Enum

if TYPE_CHECKING:
    from modules.shell.shell import ShellSession


T = TypeVar("T")

TRUEISH = ["+", "1", "true", "t", "yes", "y"]
FALSEISH = ["-", "0", "false", "f", "no", "n"]
BOOLEAN_VALUES = TRUEISH + FALSEISH

commands_register: list["Command"] = []


@dataclass
class _ParamT(Generic[T]):
    name: str
    validator: Callable[[str], bool]
    factory: Callable[[str], T]
    
    
class _BaseType(Enum):
    TEXT = _ParamT[str]("Text", lambda _: True, lambda x: x)
    NUMBER = _ParamT[int]("Number", lambda x: x.isnumeric(), lambda x: int(x))
    BOOL = _ParamT[bool]("Boolean", lambda x: x.lower() in BOOLEAN_VALUES, lambda x: True if x.lower() in TRUEISH else False)
    

@dataclass
class Parameter(Generic[T]):
    name: str
    type: _BaseType
    default: T | None = None
    
    def __repr__(self) -> str:
        return self.full_help()
    
    def full_help(self) -> str:
        """ Returns parameter information including name, type and default value. """
        pre = "<" if self.default is None else "["
        suf = ">" if self.default is None else "]"
        default_info = "" if self.default is None else f"{style.Style.DIM} = {style.ITALIC}`{str(self.default)}`{style.RESET}"
        name = f"{self.name}?" if self.default is not None else f"{style.UNDERLINE}{self.name}{style.RESET}" 
        type = style.tcolor(self.type.value.name, style.PRIMARY, styles=[style.AnsiStyle.ITALIC])

        return f"{style.tcolor(pre, style.PRIMARY, styles=[style.AnsiStyle.DIM])}{name}{style.Fore.LIGHTBLACK_EX}: {type}{default_info}{style.tcolor(suf, style.PRIMARY, styles=[style.AnsiStyle.DIM])}{style.RESET}"
        
    def brief_help(self) -> str:
        """ Returns only parameter's name and if is required. """
        pre = "<" if self.default is None else "["
        suf = ">" if self.default is None else "]"
        name = f"{self.name}?" if self.default is not None else f"{style.UNDERLINE}{self.name}{style.RESET}" 
        
        return f"{style.tcolor(pre, style.PRIMARY, styles=[style.AnsiStyle.DIM])}{name}{style.tcolor(suf, style.PRIMARY, styles=[style.AnsiStyle.DIM])}"
        

@dataclass
class Command:
    name: str
    group: str
    aliases: list[str] = field(default_factory=[])
    params: list[Parameter] = field(default_factory=[])
    req_perms: perms.PermissionType | None = None
    docs: str = ""
    callback: Callable[["ShellSession", dict[str, Any]], None] = None
    
    def __post_init__(self) -> None:
        commands_register.append(self)

    def help_inline(self) -> str:
        name = style.tcolor(self.name, style.PRIMARY)
        params = ' '.join(param.brief_help() for param in self.params)
        return f"{name} {params} - {style.ITALIC}{self.docs} {style.colored_type(self.req_perms)}"
    
    def help_full(self) -> str:
        primary = lambda s: style.tcolor(s, style.PRIMARY)
        dot = f"{style.Style.DIM}•{style.RESET}"

        header = f"\n╭───{style.Fore.LIGHTBLACK_EX}({style.RESET} Documentation {style.tcolor('::', style.PRIMARY)} {style.tcolor(f' {self.name} ', style.AnsiFGColor.BLACK, bg_color=style.PRIMARY)} {style.Fore.LIGHTBLACK_EX}){style.RESET}\n│\n"
        group = f"│ {dot} {primary('Group')}:\n│\t{self.group.value}\n│\n"
        aliases = f"│ {dot} {primary('Aliases')}:\n│\t{style.ITALIC}{style.SEP.join(self.aliases)}{style.RESET}\n│\n"
        params = f"│ {dot} {primary('Parameters')}:\n│\t{' '.join(repr(param) for param in self.params)}\n│\n"
        req_perms = f"│ {dot} {primary('Permissions')}:\n│\t{style.colored_type(self.req_perms)}\n│\n"
        docs = f"│ {dot} {primary('Information')}:\n│\t{style.ITALIC}{self.docs}{style.RESET}\n│\n"
        tail = f"{primary('•')}\n"

        return header + group + aliases + params + req_perms + docs + tail

    def call(self, session: "ShellSession", params: dict[str, Any]) -> None:
        self.callback(session, params)


class CommandsGroups(Enum):
    SYSTEM = "System."
    MANAGEMENT = "Management."
    FILE_SYSTEM = "File system."
    DEBUG = "Debug."


""" SYSTEM COMMANDS. """

Command(
    name="help",
    group=CommandsGroups.SYSTEM,
    aliases=["?"],
    params=[Parameter("CmdName", _BaseType.TEXT, "")],
    req_perms=None,
    docs="Display list of all commands with their brief help (name, attrs, docs and permissions) or displays full documentation of a specified command in `cmdName?` parameter.",
    callback=interaction.help_command
)

Command(
    name="exit",
    group=CommandsGroups.SYSTEM,
    aliases=["quit", "q"],
    params=[Parameter("Logout", _BaseType.BOOL, False)],
    req_perms=None,
    docs="Exit program. Erease login data if `Logout` parameter is set to True.",
    callback=interaction.exit_command
)

Command(
    name="logout",
    group=CommandsGroups.SYSTEM,
    aliases=[],
    params=[],
    req_perms=None,
    docs="Exit program, erease login data and burn current access token. Equivalent to `exit yes`",
    callback=interaction.logout_command
)

Command(
    name="switch",
    group=CommandsGroups.SYSTEM,
    aliases=["instance"],
    params=[],
    req_perms=None,
    docs="Switch current working instance. Opens select menu.",
    callback=interaction.switch_instance_command
)


""" MANAGEMENT COMMANDS. """

Command(
    name="members",
    group=CommandsGroups.MANAGEMENT,
    aliases=["users"],
    params=[Parameter("ShowID", _BaseType.BOOL, False)],
    req_perms=perms.PermissionType.READ,
    docs="View list of all instance members and their permissions.",
    callback=interaction.list_members
)

Command(
    name="perms",
    group=CommandsGroups.MANAGEMENT,
    aliases=["permissions"],
    params=[Parameter("member", _BaseType.TEXT), Parameter("privileges", _BaseType.TEXT)],
    req_perms=perms.PermissionType.ADMIN,
    docs="Update member's permissions. OWNER's permissions cannot be changed. ADMIN's permissions can be changed ONLY by OWNER. "
         "Only OWNER can assign @Admin permissions. "
         "Use `a`, `r`, `w` for @Admin, @Read and @Write permissions in `privileges`. For example to give user access to "
         "@Read and @Write interactions, use `rw`. @Admin automatically gives permissions to @Read and @Write.",
    callback=interaction.manage_perms
)


""" FILE SYSTEM """

Command(
    name="ls",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=["dir"],
    params=[Parameter("Recursive", _BaseType.BOOL, False)],
    req_perms=perms.PermissionType.READ,
    docs="Display list of all files and dirs in tree-view.",
    callback=interaction.list_dir
)

Command(
    name="cd",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=[],
    params=[Parameter("Path", _BaseType.TEXT)],
    req_perms=perms.PermissionType.READ,
    docs="Change current working directory (CWD) to given path.",
    callback=interaction.change_directory
)

Command(
    name="home",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=["~"],
    params=[],
    req_perms=perms.PermissionType.READ,
    docs="Change current working directory to the home (~/) path.",
    callback=interaction.cd_home
)

Command(
    name="mkfile",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=["mkf", "touch"],
    params=[Parameter("Path", _BaseType.TEXT)],
    req_perms=perms.PermissionType.WRITE,
    docs="Create new file in specified path from CWD. `mkfile a/b.txt` will create file b.txt in ./a",
    callback=interaction.make_file
)

Command(
    name="mkdir",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=["mkd"],
    params=[Parameter("Path", _BaseType.TEXT)],
    req_perms=perms.PermissionType.WRITE,
    docs="Create new directory in specified path from CWD. `mkdir a/b` will create dir b in ./a",
    callback=interaction.make_dir
)

Command(
    name="remove",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=["rm", "del", "delete"],
    params=[Parameter("Path", _BaseType.TEXT)],
    req_perms=perms.PermissionType.WRITE,
    docs="Delete specified object. It will remove directory recursively.",
    callback=interaction.remove_object
)

Command(
    name="rename",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=["ren"],
    params=[Parameter("Path", _BaseType.TEXT), Parameter("NewName", _BaseType.TEXT)],
    req_perms=perms.PermissionType.WRITE,
    docs="Rename specified object. NewName must not exist in object's directory.",
    callback=interaction.rename_object
)

Command(
    name="read",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=["cat"],
    params=[Parameter("Path", _BaseType.TEXT)],
    req_perms=perms.PermissionType.READ,
    docs="Read file's content. Displays content in terminal.",
    callback=interaction.read_file
)

Command(
    name="download",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=["pull", "get"],
    params=[Parameter("Path", _BaseType.TEXT), Parameter("Override", _BaseType.BOOL, False)],
    req_perms=perms.PermissionType.READ,
    docs="Download file or directory of files. Files are saved in ./downloads/DRIVE_NAME/. When pulling directories, they are saved in ZIP format. (Blank directories are skipped)",
    callback=interaction.pull_object
)

Command(
    name="edit",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=["edt", "write"],
    params=[Parameter("Path", _BaseType.TEXT)],
    req_perms=perms.PermissionType.WRITE,
    docs="Edit files content. Opens text editor with editable content. After editing save and close file to upload it.",
    callback=interaction.edit_file
)

Command(
    name="push",
    group=CommandsGroups.FILE_SYSTEM,
    aliases=["up", "upload"],
    params=[Parameter("LocalPath", _BaseType.TEXT)],
    req_perms=perms.PermissionType.WRITE,
    docs="Upload local file to the Drive in current path.",
    callback=interaction.upload_file
)


""" DEBUG """

Command(
    name="usage",
    group=CommandsGroups.DEBUG,
    aliases=[],
    params=[],
    req_perms=perms.PermissionType.READ,
    docs="Check total memory used and usage per bucket.",
    callback=interaction.get_usage
)

Command(
    name="cachedump",
    group=CommandsGroups.DEBUG,
    aliases=["cache"],
    params=[Parameter("BucketIndex", _BaseType.NUMBER, 0)],
    req_perms=perms.PermissionType.ADMIN,
    docs="Display cache dump for specified bucket. Format: `ChannelID: SizeB` (advanced)",
    callback=interaction.dump_cache
)

Command(
    name="recache",
    group=CommandsGroups.DEBUG,
    aliases=[],
    params=[Parameter("BucketIndex", _BaseType.NUMBER, 0)],
    req_perms=perms.PermissionType.ADMIN,
    docs="Recalculate cache for specified bucket. (advanced)",
    callback=interaction.recache
)

Command(
    name="trace",
    group=CommandsGroups.DEBUG,
    aliases=[],
    params=[Parameter("Path", _BaseType.TEXT)],
    req_perms=perms.PermissionType.ADMIN,
    docs="Trace the route of file's content in memory. Outputs list of messages, amount of chunks and header address. (advanced)",
    callback=interaction.trace_file
)



