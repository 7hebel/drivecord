from modules.paths import sizeof_fmt

from dataclasses import dataclass, field
from collections.abc import Generator
import discord

HOME_DIR = "~/"
ILLEGAL_CHARS = "\\/:*?<>|\"~` "
BLANK_FILE_CONTENT = ""
MAX_NAME_LEN = 256


def is_object_name_valid(name: str) -> bool:
    if not name or len(name) > MAX_NAME_LEN:
        return False

    for char in name:
        if char in ILLEGAL_CHARS:
            return False

    return True


class Tokens:
    TYPE_DIR = "D"
    TYPE_FILE = "F"
    END_OBJ = "|"
    OUT_DIR = "?"


@dataclass
class MemoryAddress:
    channel_id: int
    message_id: int

    @staticmethod
    def from_message(message: discord.Message) -> "MemoryAddress":
        return MemoryAddress(
            channel_id=message.channel.id,
            message_id=message.id
        )

    def __post_init__(self) -> None:
        self.channel_id = int(self.channel_id)
        self.message_id = int(self.message_id)

    def prepare_mem_addr(self) -> str:
        return f"{self.channel_id}:{self.message_id}"


@dataclass
class _FS_Obj:
    name: str
    parent_dir: "FS_Dir"

    def __post_init__(self) -> None:
        if self.parent_dir is not None:
            if isinstance(self, FS_File):
                self.parent_dir.insert_file(self)
            if isinstance(self, FS_Dir):
                self.parent_dir.insert_dir(self)

    def path_to(self) -> str:
        ...
        
    def api_export(self) -> dict:
        ...

    def base_dir(self) -> "FS_Dir | _FS_Obj":
        if self.parent_dir is not None:
            return self.parent_dir.base_dir()
        return self

    def remove(self) -> bool:
        if self.name == "~":
            return False

        if isinstance(self, FS_File):
            self.parent_dir.files.remove(self)

        if isinstance(self, FS_Dir):
            self.parent_dir.dirs.remove(self)

        self.parent_dir = None
        return True

    def is_linked(self) -> bool:
        """ Check if entire path trace exists to this point. """
        if self.name == '~':
            return True

        trace = self.path_to().split("/")[::-1][2:]  # .., ../..

        if not trace:
            return False
        if trace[-1] != "~":
            return False

        parent = self.parent_dir
        child = self

        for name in trace:
            if parent.name != name:
                return False

            if child not in parent.files and child not in parent.dirs:
                return False

            child = parent
            parent = parent.parent_dir

        return True


@dataclass
class FS_File(_FS_Obj):
    mem_addr: MemoryAddress
    size: int

    def repr(self) -> str:
        return f"{Tokens.TYPE_FILE}:{self.name}:{self.mem_addr.prepare_mem_addr()}:{self.size}{Tokens.END_OBJ}"

    def path_to(self, t=[]) -> str:
        t.append(self.name)

        if self.parent_dir is not None:
            return self.parent_dir.path_to(t).removesuffix("/")

        trace = t[::-1]
        path = "/".join(trace)
        return path
    
    def api_export(self) -> dict:
        return {
            "type": Tokens.TYPE_FILE,
            "name": self.name,
            "path": self.path_to(),
            "size": self.size
        }


@dataclass
class FS_Dir(_FS_Obj):
    files: list[FS_File] = field(default_factory=list)
    dirs: list["FS_Dir"] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.parent_dir is not None:
            if isinstance(self, FS_File):
                self.parent_dir.insert_file(self)
            if isinstance(self, FS_Dir):
                self.parent_dir.insert_dir(self)

    def insert_file(self, file: FS_File) -> None:
        if file.parent_dir is None:
            file.parent_dir = self
        if file not in self.files:
            self.files.append(file)

    def insert_dir(self, dir: "FS_Dir") -> None:
        if dir.parent_dir is None:
            dir.parent_dir = self
        if dir not in self.dirs:
            self.dirs.append(dir)

    def has_object(self, name: str) -> bool:
        for d in self.dirs:
            if d.name == name:
                return True

        for f in self.files:
            if f.name == name:
                return True

        return False

    def path_to(self, t=[]) -> str:
        t.append(self.name)

        if self.parent_dir is not None:
            return self.parent_dir.path_to(t)

        trace = t[::-1]
        path = "/".join(trace)
        t.clear()
        return path + "/"

    def draw_tree(self, _depth: int = 0, _buff: str = "") -> str:
        _buff += f"{'| ' * _depth}[{self.name}]\n"

        d = '| ' * (_depth + 1)
        for file in self.files:
            _buff += d + file.name + f" ({sizeof_fmt(file.size)})" + "\n"

        for dir in self.dirs:
            _buff = dir.draw_tree(_depth + 1, _buff)

        return _buff
    
    def api_export(self) -> dict:
        this_data = {
            "type": Tokens.TYPE_DIR,
            "name": self.name,
            "path": self.path_to(),
            "files": [],
            "dirs": [] 
        }
        
        for file in self.files:
            this_data["files"].append(file.api_export())
            
        for dir in self.dirs:
            this_data["dirs"].append(dir.api_export())
        
        return this_data
        
    def export(self) -> str:
        base = f"{Tokens.TYPE_DIR}:{self.name}{Tokens.END_OBJ}"

        for file in self.files:
            base += file.repr()

        for dir in self.dirs:
            base += dir.export()

        base += f"{Tokens.OUT_DIR}"
        return base

    def move_to(self, rel_path: str) -> _FS_Obj | None:
        """ Returns FS_Dir or FS_File at given relative path. None if invalid. """
        rel_path = rel_path.replace("\\", "/")
        cwd = self

        for i, part in enumerate(rel_path.split("/")):
            if not part:
                continue

            if part == "~":
                if i != 0:
                    return None
                cwd = self.base_dir()
                continue

            if isinstance(cwd, FS_File):
                return None

            if part == ".":
                continue

            if part == "..":
                cwd = cwd.parent_dir
                continue

            for d in cwd.dirs:
                if d.name == part:
                    cwd = d
                    break
            else:
                for f in cwd.files:
                    if f.name == part:
                        cwd = f
                        break
                else:
                    return None

        return cwd

    def walk(self, file_only: bool = False) -> Generator[_FS_Obj]:
        for file in self.files:
            yield file

        for dir in self.dirs:
            if not file_only:
                yield dir

            for item in dir.walk(file_only=file_only):
                yield item
