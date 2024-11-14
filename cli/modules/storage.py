import keyring

_SERVICE_NAME = "DriveCord"
_TOKEN_NAME = "accessToken"
_UID_NAME = "userID"


def init() -> None:
    if load_access_token() and not load_user_id():
        reset_access_token()


def load_access_token() -> str | None:
    return keyring.get_password(_SERVICE_NAME, _TOKEN_NAME)

def set_access_token(token: str) -> None:
    keyring.set_password(_SERVICE_NAME, _TOKEN_NAME, token)

def reset_access_token() -> None:
    keyring.delete_password(_SERVICE_NAME, _TOKEN_NAME)


def load_user_id() -> int | None:
    uid = keyring.get_password(_SERVICE_NAME, _UID_NAME)
    if uid is not None:
        return int(uid)

def set_user_id(uid: int) -> None:
    keyring.set_password(_SERVICE_NAME, _UID_NAME, str(uid))

def reset_user_id() -> None:
    keyring.delete_password(_SERVICE_NAME, _UID_NAME)


def reset_all():
    reset_access_token()
    reset_user_id()
