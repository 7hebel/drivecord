from modules.tui import style
from modules import fs


_FOLDER_CLOSED_ICON = "📁"
_FOLDER_OPENNED_ICON = "📂"
_FILE_ICON = "📄"
_LVL_LINE = f"{style.Fore.LIGHTBLACK_EX}│ {style.RESET}"

class TreeView:
    def __init__(self, base: fs.FS_Dir, recursive: bool) -> None:
        self.dir = base
        self.recursive = recursive
        
        self.__draw_level = 1
        self.__dir_icon = _FOLDER_CLOSED_ICON if not recursive else _FOLDER_OPENNED_ICON
        print(f"\n╭───{style.Fore.LIGHTBLACK_EX}<{style.RESET} {base.path_to} {style.Fore.LIGHTBLACK_EX}>{style.RESET}\n│")
        
    def __get_lvl_prefix(self, for_dir: bool = False, is_last_dir: bool = False) -> str:
        if for_dir:
            if self.__draw_level == 1:
                return "│ "
            
            dir_entry = "├─" if not is_last_dir else "╰─"
            return "│ " + _LVL_LINE * (self.__draw_level - 2) + f"{style.Fore.LIGHTBLACK_EX}{dir_entry}{style.RESET}"

        return "│ " + _LVL_LINE * (self.__draw_level - 1)
        

    def __higher(self) -> None:
        if self.__draw_level > 0:
            self.__draw_level -= 1
            
    def __deeper(self) -> None:
        self.__draw_level += 1
        
    def __draw_file(self, file: fs.FS_File) -> None:
        size = fs.sizeof_fmt(file.size)
        content = f"{_FILE_ICON} {file.name}  {style.tcolor(f'({size})', style.AnsiFGColor.LBLACK, styles=[style.AnsiStyle.ITALIC])}"
        line = self.__get_lvl_prefix() + content
        print(line)
        
    def __draw_dir(self, dir: fs.FS_Dir, _last_dir: bool = False) -> None:
        name = dir.name
        size = fs.sizeof_fmt(dir.calc_size())
        content = f"{self.__dir_icon} {style.tcolor(name, style.AnsiFGColor.CYAN)}  {style.tcolor(f'({size})', style.AnsiFGColor.LBLACK, styles=[style.AnsiStyle.ITALIC])}"
        line = self.__get_lvl_prefix(for_dir=True, is_last_dir=_last_dir) + content
        print(line)
        
        if self.recursive:
            self.__deeper()
            
            for file in dir.files:
                self.__draw_file(file)
                
            for di, d in enumerate(dir.dirs, 1):
                self.__draw_dir(d, di==len(dir.dirs))
                
            self.__higher()

    def draw(self) -> None:
        for file in self.dir.files:
            self.__draw_file(file)
            
        for dir in self.dir.dirs:
            self.__draw_dir(dir)
        
    def finish(self) -> None:
        print(f"│\n{style.tcolor('•', style.PRIMARY)}\n")    
