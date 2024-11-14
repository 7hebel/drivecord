from modules.tui import list_view
from modules.tui import style
from modules import storage

from typing import TYPE_CHECKING
from http import HTTPStatus
import requests
import sys

if TYPE_CHECKING:
    from modules.shell.shell import ShellSession


API_ADRESSS = "http://localhost:8000/api/"


def _validate_server_response(response: requests.Response) -> bool:
    """ Check for validation error status codes. Returns if can continue. Prints errors if any. """
    if response.status_code == HTTPStatus.UNAUTHORIZED:
        print(style.error_msg("Client authentication failed."))
        sys.exit(1)
    
    if response.status_code == HTTPStatus.FORBIDDEN:
        print(style.error_msg("You are not member of this Drive..."))
        return False
    
    if response.status_code == HTTPStatus.NOT_IMPLEMENTED:
        print(style.error_msg("Drive not found..."))
        return False
        
    if response.status_code == HTTPStatus.CONFLICT:
        print(style.error_msg(response.text))
        return False
        
    return True
        

def _request_error(exc: Exception) -> None:
    print(style.error_msg(f"Request error: {exc}"))
    sys.exit(1)


def _auth() -> dict:
    return {"uid": storage.load_user_id(), "token": storage.load_access_token()}


def check_api_status() -> bool:
    try:
        status = requests.get(API_ADRESSS, timeout=3)
        return status.status_code == HTTPStatus.OK
        
    except:
        return False


class AccessAPI:
    endpoint_base = API_ADRESSS + "access/"
    
    @staticmethod
    def validate_saved_login_data() -> bool:
        saved_token = storage.load_access_token()
        saved_uid = storage.load_user_id()
        if saved_token is None or saved_uid is None:
            return False
        
        try:
            status_endpoint = AccessAPI.endpoint_base + f"validateToken/{saved_uid}/{saved_token}"
            status = requests.get(status_endpoint).status_code
            
            if status == HTTPStatus.OK:
                print(style.success_msg("Logged in using saved access token"))
                return True
                
            storage.reset_all()
                
            if status == HTTPStatus.NOT_FOUND:
                print(style.error_msg("Invalid user id found."))
                return False
            
            if status == HTTPStatus.UNAUTHORIZED:
                print(style.error_msg("Invalid access token found."))
                return False
                
            return False
        
        except Exception as exc:
            storage.reset_all()
            return _request_error(exc)

    @staticmethod
    def validate_uid(uid: int) -> bool:
        try:
            status_endpoint = AccessAPI.endpoint_base + f"validateUID/{uid}"
            status = requests.get(status_endpoint).status_code
            
            if status == HTTPStatus.OK:
                return True
            
            return False

        except Exception as exc:
            return _request_error(exc)
        
    @staticmethod
    def login(uid: int, password: str) -> bool:
        try:
            status_endpoint = AccessAPI.endpoint_base + "login"
            status = requests.post(status_endpoint, json={"uid": uid, "password": password}).status_code
            
            if status == HTTPStatus.OK:
                return True

            if status == HTTPStatus.NOT_FOUND:
                return False
            
            return False

        except Exception as exc:
            return _request_error(exc)

    @staticmethod
    def get_access_token(uid: int, password: str) -> str | None:
        try:
            status_endpoint = AccessAPI.endpoint_base + "getToken"
            response = requests.post(status_endpoint, json={"uid": uid, "password": password})
            status = response.status_code
            
            if status == HTTPStatus.OK:
                print(style.success_msg("Fetched access token."))
                return response.text
            
            if status == HTTPStatus.UNAUTHORIZED:
                print(style.error_msg("Invalid password."))
                return None
            
            if status == HTTPStatus.NOT_ACCEPTABLE:
                print(style.error_msg("Access tokens limit exceeded. Logout from other clients or manage tokens via Discord Bot."))
                return None
            
        except Exception as exc:
            return _request_error(exc)

    @staticmethod
    def logout() -> None:
        try:
            status_endpoint = AccessAPI.endpoint_base + "logout"
            response = requests.post(status_endpoint, json=_auth())
            status = response.status_code
            
            if status == HTTPStatus.OK:
                print(style.success_msg("Logged out."))
            
            if status == HTTPStatus.UNAUTHORIZED:
                print(style.error_msg("Logout operation not authorized. (Invalid IP address)"))
            
            if status == HTTPStatus.NOT_FOUND:
                print(style.error_msg("Already logged out."))

        except Exception as exc:
            return _request_error(exc)


class InstanceAPI:
    endpoint_base = API_ADRESSS + "instance/"
  
    @staticmethod
    def fetch_user_instances() -> dict[int, str] | None:
        try:
            status_endpoint = InstanceAPI.endpoint_base + "fetchAll"
            response = requests.post(status_endpoint, json=_auth())
            status = response.status_code
            
            if not _validate_server_response(response):
                return
            
            if status == HTTPStatus.OK:
                print(style.success_msg("Fetched user instances."))
                return response.json()
            
        except Exception as exc:
            return _request_error(exc)
    
    def __init__(self, instance_id: int) -> None:
        self.endpoint_base = InstanceAPI.endpoint_base + f"{instance_id}/"
            
    def fetch_perms(self) -> dict[str, bool] | None:
        try:
            status_endpoint = self.endpoint_base + "getPerms"
            response = requests.post(status_endpoint, json=_auth())
            status = response.status_code
            
            if not _validate_server_response(response):
                return
            
            if status == HTTPStatus.OK:
                return response.json()
            
        except Exception as exc:
            return _request_error(exc)
    
    def fetch_members(self) -> list[list[str, int, dict[str, bool] | bool]]:
        """ Returns list of [NAME, ID, RAW_PERMS/False] for all instance members. perms=False if user is not registered. """
        try:
            status_endpoint = self.endpoint_base + "fetchMembers"
            response = requests.post(status_endpoint, json=_auth())
            status = response.status_code
            
            if not _validate_server_response(response):
                return

            if status == HTTPStatus.OK:
                return response.json()

        except Exception as exc:
            return _request_error(exc)
        
    def update_perms(self, member_id: int, permissions: dict[str, bool]) -> None:
        try:
            status_endpoint = self.endpoint_base + "updatePerms"
            data = {"member_id": member_id, "perms": permissions}
            data.update(_auth())
            
            response = requests.post(status_endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return
            
            if status == HTTPStatus.OK:
                print(style.success_msg("Updated permissions."))
                return None

        except Exception as exc:
            return _request_error(exc)
        
        
class FileSystemAPI:
    endpoint_base = API_ADRESSS + "fs/"
  
    def __init__(self, shell: "ShellSession", instance_id: int) -> None:
        self.shell = shell
        self.endpoint_base = FileSystemAPI.endpoint_base + f"{instance_id}/"
        
    def __cwd_auth_data(self) -> dict[str, str]:
        auth_data = _auth()
        auth_data.update({"cwd": self.__get_cwd()})
        return auth_data
        
    def __get_cwd(self) -> str:
        return self.shell.cwd.path_to
    
    def get_struct(self) -> dict:
        try:
            endpoint = self.endpoint_base + "structure"

            response = requests.post(endpoint, json=_auth())
            status = response.status_code
            
            if not _validate_server_response(response):
                return

            if status == HTTPStatus.OK:
                return response.json()
            
        except Exception as exc:
            return _request_error(exc)
        
    def make_file(self, path: str) -> None:
        try:
            endpoint = self.endpoint_base + "mkfile"
            data = self.__cwd_auth_data()
            data.update({"path": path})
            
            response = requests.post(endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return

            if status == HTTPStatus.OK:
                self.shell.update_struct()
                print(style.success_msg(f"Created file: {path}"))
            
        except Exception as exc:
            return _request_error(exc)
        
    def make_dir(self, path: str) -> None:
        try:
            endpoint = self.endpoint_base + "mkdir"
            data = self.__cwd_auth_data()
            data.update({"path": path})
            
            response = requests.post(endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return

            if status == HTTPStatus.OK:
                self.shell.update_struct()
                print(style.success_msg(f"Created directory: {path}"))
                    
        except Exception as exc:
            return _request_error(exc)
        
    def remove_object(self, path: str) -> None:
        try:
            endpoint = self.endpoint_base + "rm"
            data = self.__cwd_auth_data()
            data.update({"path": path})
            
            response = requests.post(endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return

            if status == HTTPStatus.OK:
                self.shell.update_struct()
                print(style.success_msg(f"Removed: {path}"))
            
        except Exception as exc:
            return _request_error(exc)
        
    def rename_object(self, path: str, new_name: str) -> None:
        try:
            endpoint = self.endpoint_base + "rename"
            data = self.__cwd_auth_data()
            data.update({"path": path, "new_name": new_name})
            
            response = requests.post(endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return

            if status == HTTPStatus.OK:
                self.shell.update_struct()
                print(style.success_msg(f"Renamed: {path} -> {new_name}"))
            
        except Exception as exc:
            return _request_error(exc)
        
    def read_file(self, path: str) -> str | bool:
        try:
            endpoint = self.endpoint_base + "read"
            data = self.__cwd_auth_data()
            data.update({"path": path})
            
            response = requests.post(endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return False

            if status == HTTPStatus.OK:
                return response.text
            
        except Exception as exc:
            return _request_error(exc)
        
    def pull_object(self, path: str) -> dict | bool:
        try:
            endpoint = self.endpoint_base + "pull"
            data = self.__cwd_auth_data()
            data.update({"path": path})
            
            response = requests.post(endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return False

            if status == HTTPStatus.OK:
                return response.json()
            
        except Exception as exc:
            return _request_error(exc)
        
    def write_file(self, path: str, content: str) -> None:
        try:
            endpoint = self.endpoint_base + "write"
            data = self.__cwd_auth_data()
            data.update({"path": path, "content": content})
            
            response = requests.post(endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return

            if status == HTTPStatus.OK:
                print(style.success_msg("Edited content."))
            
        except Exception as exc:
            return _request_error(exc)
        
    def upload_file(self, path: str, content: str) -> None:
        try:
            endpoint = self.endpoint_base + "upload"
            data = self.__cwd_auth_data()
            data.update({"path": path, "content": content})
            
            response = requests.post(endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return

            if status == HTTPStatus.OK:
                self.shell.update_struct()
                print(style.success_msg("File uploaded."))
            
        except Exception as exc:
            return _request_error(exc)
        
        
class DebugAPI:
    endpoint_base = API_ADRESSS + "dbg/"

    def __init__(self, instance_id: int) -> None:
        self.endpoint_base = DebugAPI.endpoint_base + f"{instance_id}/"

    def get_memory_usage(self) -> None:
        try:
            status_endpoint = self.endpoint_base + "memusage"
            
            response = requests.post(status_endpoint, json=_auth())
            status = response.status_code
            
            if not _validate_server_response(response):
                return
            
            if status == HTTPStatus.OK:
                data = response.json()

                total = data.get("total")
                per_bucket = data.get("per_bucket")
                
                print(f"\nTotal memory used: {style.tcolor(total, style.PRIMARY)}")
                
                buckets_list = list_view.ListView("Usage per bucket.")
                for bucket, usage in per_bucket.items():
                    buckets_list.item(f"{style.tcolor(bucket, style.PRIMARY)}: {style.ITALIC}{usage}{style.RESET}")
                
                buckets_list.finish()

        except Exception as exc:
            return _request_error(exc)
    

    def dump_cache(self, index: int = 0) -> None:
        try:
            status_endpoint = self.endpoint_base + "dumpcache"
            data = _auth()
            data.update({"index": index})
            
            response = requests.post(status_endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return
            
            if status == HTTPStatus.OK:
                cache = response.text
                
                print(f"\n{style.tcolor(f'data_{index}', style.PRIMARY)} bucket cache:\n")
                print(cache)

        except Exception as exc:
            return _request_error(exc)
    

    def recache(self, index: int = 0) -> None:
        try:
            status_endpoint = self.endpoint_base + "recache"
            data = _auth()
            data.update({"index": index})
            
            response = requests.post(status_endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return
            
            if status == HTTPStatus.OK:
                print(style.success_msg("Recalculated bucket's cache."))
                
                cache = response.text
                
                print(f"\n{style.tcolor(f'data_{index}', style.PRIMARY)} recalculated bucket cache:\n")
                print(cache)

        except Exception as exc:
            return _request_error(exc)
    
    def trace_file(self, path: str) -> None:
        try:
            status_endpoint = self.endpoint_base + "trace"
            data = _auth()
            data.update({"path": path})
            
            response = requests.post(status_endpoint, json=data)
            status = response.status_code
            
            if not _validate_server_response(response):
                return
            
            if status == HTTPStatus.OK:
                print(style.success_msg("Found file trace."))

                trace = response.json()
                
                for i, (id, url) in enumerate(trace):
                    indent = "  " * i + style.tcolor("╰> ", style.PRIMARY) if i != 0 else "\n"
                    content = f"{style.ITALIC}{id}{style.RESET} ({style.UNDERLINE}{url}{style.RESET})"
                    print(indent + content)
                
        except Exception as exc:
            return _request_error(exc)
        
    