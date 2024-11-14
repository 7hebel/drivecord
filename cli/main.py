from modules.tui.style import set_title, error_msg, success_msg
from modules.tui import inputs, text
from modules.shell import shell
from modules import storage
from modules import api

import sys


print(set_title("☁️ DriveCord CLI"), end="")


storage.init()

api_status = api.check_api_status()
if not api_status:
    print(error_msg(f"Couldn't connect to API. ({api.API_ADRESSS})"))
    sys.exit(1)
else:
    print(success_msg("Connected to API."))
    

def manual_login() -> None:
    print(text.header("Login to DriveCord.", emoji="☁️"))

    def _validate_uid(value: str):
        if not api.AccessAPI.validate_uid(value):
            raise ValueError("There is no DriveCord account with this ID. If You don't have DriveCord account yet, create one using Discord Bot")

    def _validate_creds(value: str):
        if not api.AccessAPI.login(uid, value):
            raise ValueError("Invalid password.")

    uid: int = inputs.Prompt(
        question="Discord user ID.",
        allowed_chars=inputs.CHARSET_DIGITS, 
        max_len=18,
        min_len=18,
        converter=int,
        validator=_validate_uid        
    ).ask()
    
    pwd: str = inputs.Prompt(
        question="DriveCord password.",
        min_len=3,
        is_password=True,
        validator=_validate_creds
    ).ask()
    
    token = api.AccessAPI.get_access_token(uid, pwd)
    if token is None:
        print(error_msg("Login failed."))
        sys.exit(1)
    
    storage.set_user_id(uid)
    storage.set_access_token(token)


if not api.AccessAPI.validate_saved_login_data():
    manual_login()


user_instances = api.InstanceAPI.fetch_user_instances()

if not user_instances:
    print(error_msg("You have no active DriveCord instances. Create new instance or join existing one."))
    sys.exit(1)
    

shell.ShellSession(user_instances).mainloop()
