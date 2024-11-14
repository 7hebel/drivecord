from modules.tui.style import error_msg

from dataclasses import dataclass, field


TYPE_DIR = "D"
TYPE_FILE = "F"


@dataclass
class FS_Obj:
    path_to: str
    name: str
    parent_dir: "FS_Dir"

    def __post_init__(self) -> None:
        if self.parent_dir is not None:
            if isinstance(self, FS_File):
                self.parent_dir.insert_file(self)
            if isinstance(self, FS_Dir):
                self.parent_dir.insert_dir(self)
                
    def base_dir(self) -> "FS_Dir":
        if self.parent_dir is not None:
            return self.parent_dir.base_dir()
        return self


@dataclass
class FS_Dir(FS_Obj):
    dirs: list["FS_Dir"] = field(default_factory=list)
    files: list["FS_File"] = field(default_factory=list)

    def calc_size(self) -> int:
        """ Calculate total size stored inside this directory recursively. """
        total_size = 0
        
        for file in self.files:
            total_size += file.size
            
        for dir in self.dirs:
            total_size += dir.calc_size()
            
        return total_size
    
    def insert_file(self, file: "FS_File") -> None:
        if file.parent_dir is None:
            file.parent_dir = self
        if file not in self.files:
            self.files.append(file)

    def insert_dir(self, dir: "FS_Dir") -> None:
        if dir.parent_dir is None:
            dir.parent_dir = self
        if dir not in self.dirs:
            self.dirs.append(dir)
    
    def move_to(self, rel_path: str) -> FS_Obj | None:
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


@dataclass
class FS_File(FS_Obj):
    size: str


def load_structure(struct_data: dict) -> FS_Dir:
    def _validate_item(data: dict) -> bool:
        return "type" in data and "name" in data and "path" in data
       
    def _load_dir_files(files: list[dict], parent: FS_Dir) -> list[FS_File]:
        fs_files = []
        
        for file in files:
            if not _validate_item(file):
                print(error_msg(f"Invalid file in structure: {file}"))
                return None
            
            path = file.get("path")
            name = file.get("name")
            size = file.get("size")
            fs_files.append(FS_File(path, name, parent, size))
        
        return fs_files

    def _load_inner_dirs(dirs: list[dict], parent: FS_Dir) -> list[FS_Dir]:
        fs_dirs = []
        
        for dir in dirs:
            if not _validate_item(dir):
                print(error_msg(f"Invalid dir in structure: {dir}"))
                return None

            path = dir.get("path")
            name = dir.get("name")
            fs_dir = FS_Dir(path, name, parent)
            fs_dir.dirs = _load_inner_dirs(dir.get("dirs"), fs_dir)
            fs_dir.files = _load_dir_files(dir.get("files"), fs_dir)
            
            fs_dirs.append(fs_dir)
            
        return fs_dirs
        
    if not _validate_item(struct_data):
        print(error_msg("Invalid structure."))
        return None
            
    base = FS_Dir("~/", "~", None)
    base.dirs = _load_inner_dirs(struct_data.get("dirs"), base)
    base.files = _load_dir_files(struct_data.get("files"), base)
    return base
        
        
def sizeof_fmt(num, suffix="b"):
    for unit in ("", "K", "M", "G"):
        if abs(num) < 1024.0:
            n = float(f"{num:3.1f}")
            if n.is_integer():
                n = f"{int(n)}"
            return f"{n}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}T{suffix}"
        
