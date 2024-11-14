from modules.tui import style


class ListView:
    def __init__(self, title: str) -> None:
        print(f"\n╭───{style.Fore.LIGHTBLACK_EX}({style.RESET} {title} {style.Fore.LIGHTBLACK_EX}){style.RESET}")
        
        self.__group_line = lambda name: f"{style.RESET}│\n├ [{style.Back.LIGHTBLACK_EX}{style.Fore.WHITE} {name} {style.RESET}]"
        self.__item_line = lambda content: f"│  {style.Style.DIM}•{style.RESET} {content}"
    
    def group(self, name: str) -> None:
        print(self.__group_line(name))
        
    def item(self, item: str) -> None:
        print(self.__item_line(item))
        
    def finish(self) -> None:
        print(f"│\n{style.tcolor('•', style.PRIMARY)}\n")    
