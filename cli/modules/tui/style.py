from modules.perms import PermissionType

from tcolorpy import tcolor, AnsiStyle, AnsiFGColor
from colorama import init, Fore, Back, Style
from colorama.ansi import set_title

init()

RESET = Fore.RESET + Back.RESET + Style.RESET_ALL
PRIMARY = (183, 170, 224)
ERR_COLOR = (247, 119, 149)
ERR_SIGN = "×"
OK_SING = "✓"
OK_COLOR = (144, 245, 151)
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
SEP = f'{Fore.LIGHTBLACK_EX},{Fore.RESET} '

prompt_line = f"│ {tcolor('~', color=PRIMARY)} {ITALIC}"
prompt_password_line = f"│ {tcolor('*', PRIMARY)} "
prompt_end = f"{RESET}│\n{Fore.GREEN}•{RESET}"


def style_input_question(question: str) -> str:
    question_line = f"\n╭───{Fore.LIGHTBLACK_EX}[ {Fore.MAGENTA}? {Fore.WHITE}{Style.BRIGHT}{tcolor(question, PRIMARY, styles=[AnsiStyle.ITALIC, AnsiStyle.BOLD])} {Style.RESET_ALL}{Fore.LIGHTBLACK_EX}]\n{RESET}│"
    return RESET + question_line


def style_input_error(err_msg: str) -> str:
    err_line = f"│ {Fore.RED}{ERR_SIGN} {RESET}{tcolor(err_msg, ERR_COLOR, styles=[AnsiStyle.ITALIC])}{RESET}\n│"
    return RESET + err_line


def style_checkbox_value(index: int, name: str) -> str:
    check_line = f"│  {RESET}{tcolor(str(index) + '.', PRIMARY, styles=[AnsiStyle.ITALIC])} {RESET}{name}"
    return check_line


def error_msg(content: str) -> str:
    err_line = f"{Fore.RED}{ERR_SIGN}{RESET} {tcolor(content, ERR_COLOR, styles=[AnsiStyle.ITALIC])}"
    return RESET + err_line


def success_msg(content: str) -> str:
    success_line = f"{Fore.GREEN}{OK_SING}{RESET} {tcolor(content, styles=[AnsiStyle.ITALIC])}"
    return RESET + success_line


def query_err_msg(msg: str) -> str:
    return f"{Fore.RED}│\n╰─{ERR_SIGN}{Fore.RESET} {msg}\n"


def get_perms_indicator(perms: PermissionType | None) -> str:
    char = "•"
    err = f"{Fore.RED}?{Fore.RESET}"

    if perms is None:
        return err

    if perms == PermissionType.OWNER:
        return tcolor(char, PRIMARY)

    if perms == PermissionType.ADMIN:
        return tcolor(char, (99, 86, 140))

    if perms == PermissionType.WRITE:
        return tcolor(char, (235, 122, 52))

    if perms == PermissionType.READ:
        return tcolor(char, (52, 168, 235))


def build_shell_prompt(instance_name: str, perms: PermissionType, cwd: str) -> str:
    perms = get_perms_indicator(perms)
    return RESET + f"\n{perms} {Style.DIM}({tcolor(instance_name, PRIMARY, styles=[AnsiStyle.ITALIC])}{Style.DIM}){Style.RESET_ALL} {tcolor(cwd, styles=[AnsiStyle.ITALIC])} {tcolor('::', PRIMARY)} "


def colored_type(t: "PermissionType | None") -> str:
    if t is None:
        return ""
    
    color = {
        PermissionType.OWNER: Fore.MAGENTA,
        PermissionType.ADMIN: Fore.RED,
        PermissionType.WRITE: Fore.YELLOW,
        PermissionType.READ: Fore.BLUE
    }.get(t)
    return f"{Fore.LIGHTBLACK_EX}@{color}{t.value}{RESET}"

