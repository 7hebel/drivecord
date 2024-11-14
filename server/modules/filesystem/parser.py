from modules.filesystem.fs import FS_Dir, FS_File, _FS_Obj, Tokens, MemoryAddress

from typing import Optional


TYPE_TOKENS = [Tokens.TYPE_DIR, Tokens.TYPE_FILE]


class Parser:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.top: FS_Dir | None = None
        self.total_objects = self.raw.count(Tokens.END_OBJ)

    def __execute_ptr_cmds(self) -> None:
        """ Execeute all increment pointer commands from content's start. """
        while self.raw and self.raw[0] == Tokens.OUT_DIR:
            self.raw = self.raw[1:]

            if self.top.parent_dir is not None:
                self.top = self.top.parent_dir

    def __parse_part(self, part: str) -> list[str, int, int, Optional[int]]:
        t = part[0]

        if t == Tokens.TYPE_FILE:
            _, name, channel_id, head_id, size = part.split(":")
            return name, int(channel_id), int(head_id), int(size)

        if t == Tokens.TYPE_DIR:
            _, name = part.split(":")
            return name

        raise ValueError(f"Cannot parse part: {part}")

    def __parse_single(self) -> _FS_Obj:
        self.__execute_ptr_cmds()

        type_char = self.raw[0]
        if type_char not in TYPE_TOKENS:
            raise ValueError(f"Invalid typechar {type_char}")

        if type_char == Tokens.TYPE_FILE:
            file_data, tail = self.raw.split(Tokens.END_OBJ, 1)
            self.raw = tail

            name, ch, head, size = self.__parse_part(file_data)
            mem = MemoryAddress(ch, head)
            return FS_File(name, self.top, mem, size)

        if type_char == Tokens.TYPE_DIR:
            dir_data, tail = self.raw.split(Tokens.END_OBJ, 1)
            self.raw = tail

            name = self.__parse_part(dir_data)
            dir_obj = FS_Dir(name, self.top)
            self.top = dir_obj
            return dir_obj

    def parse(self) -> _FS_Obj:
        base_object = self.__parse_single()

        for _ in range(self.total_objects - 1):
            self.__parse_single()

        return base_object


# _mem_addr = MemoryAddress(0, 0)

# home = FS_Dir("~", None)
# tod = FS_File("todo", home, _mem_addr, 10)
# animals = FS_Dir("animals", home)
# food = FS_Dir("food", home)
# mc = FS_Dir("mc", food)
# a = FS_Dir("a", mc)
# b = FS_Dir("b", a)
# c = FS_Dir("c", b)
# d = FS_Dir("d", c)
# x = FS_File("x", d, _mem_addr, 0)
# kfc = FS_Dir("kfc", food)
# n = FS_File("n", kfc, _mem_addr, 0)
# cats = FS_Dir("cats", animals)
# dogs = FS_Dir("dogs", animals)
# hamsters = FS_Dir("hamsters", animals)
# pig = FS_File("pig.txt", animals, _mem_addr, 123)
# c1 = FS_File("c1.txt", cats, _mem_addr, 12)
# c2 = FS_File("c2.txt", cats, _mem_addr, 16)
# d1 = FS_File("d1.txt", dogs, _mem_addr, 52)
# d2 = FS_File("d2.txt", dogs, _mem_addr, 86)

# print(home.api_export())

# for x in home.walk():
#     print(x.name, x.path_to())
# print(home.draw_tree())
