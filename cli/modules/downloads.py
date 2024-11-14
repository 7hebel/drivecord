from modules.tui import style

from datetime import datetime
import zipfile
import base64
import os

ROOT_DOWNLOADS_DIR = "./downloads/"


def ensure_downloads_directory(drive_name: str) -> None:
    if not os.path.exists(ROOT_DOWNLOADS_DIR):
        os.mkdir(ROOT_DOWNLOADS_DIR)
        print(style.success_msg("Created ./downloads/ directory in current path."))
        
    drive_dir = ROOT_DOWNLOADS_DIR + drive_name + "/"
    if not os.path.exists(drive_dir):
        os.mkdir(drive_dir)
        print(style.success_msg(f"Created {drive_name}'s downloads directory."))
    

def handle_pulled_data(drive_name: str, data: dict, override: bool) -> None:
    ensure_downloads_directory(drive_name)
    
    filename = data.get("name")
    content = data.get("content")
    is_zip = data.get("is_zip")
    
    if is_zip:
        content = base64.b64decode(content)
    
    pull_target = ROOT_DOWNLOADS_DIR + drive_name + "/" + filename
    if os.path.exists(pull_target):
        if override:
            os.remove(pull_target)
            print(f"Overriding existing {style.tcolor(filename, style.PRIMARY)} file.")

        else:
            name, ext = os.path.splitext(filename)
            timepart = f"_{int(datetime.now().timestamp())}"

            filename = name + timepart
            if ext:
                filename +=  "." + ext

            pull_target = ROOT_DOWNLOADS_DIR + drive_name + "/" + filename

            print(f"File already saved, override disabled. Saving as: {style.tcolor(filename, style.PRIMARY)}")
    
    open_mode = "a+b" if is_zip else "a+"
    with open(pull_target, open_mode) as file:
        file.write(content)

    print(style.success_msg(f"Downloaded: {style.tcolor(filename, style.PRIMARY)}"))
        