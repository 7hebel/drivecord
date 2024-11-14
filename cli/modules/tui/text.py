from modules.tui import style


def header(message: str, emoji: str = "") -> str:
    line_len = len(message) + 6

    message = style.tcolor(message, style.PRIMARY, styles=[style.AnsiStyle.BOLD, style.AnsiStyle.ITALIC]) + style.RESET
    if emoji:
        message = f"{emoji} :: {message}"
        line_len += len(emoji) + 4

    content = "\n╭" + "─" * (line_len - 2) + "╮\n"
    content += "│" + " " * (line_len - 2) + "│\n"
    content += "│  " + message + "  │\n"
    content += "│" + " " * (line_len - 2) + "│\n"
    content += "╰" + "─" * (line_len - 2) + "╯\n"
    
    return content
    

