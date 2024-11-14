from modules.tui import style


def display_content(filename: str, content: str) -> None:
    total_lines = content.count("\n") + 1
    line_field_len = len(str(total_lines))

    print(f"\nFile : {style.Fore.LIGHTBLACK_EX}[{style.RESET} {style.tcolor(filename, style.PRIMARY)} {style.Fore.LIGHTBLACK_EX}]{style.RESET}")
    print(f"Size : {style.tcolor(f'{len(content)}b', style.PRIMARY)} {style.RESET}")
    print(f"Lines: {style.tcolor(str(total_lines), style.PRIMARY)} {style.RESET}\n")

    for line, content in enumerate(content.split("\n"), 1):
        line = str(line).ljust(line_field_len)
        print(f"  {style.tcolor(line, style.PRIMARY)} {style.Fore.LIGHTBLACK_EX}│ {style.RESET}{content}")

    print("")    
    
