from pydantic import BaseModel


class AccountLogin(BaseModel):
    uid: int
    password: str


class GetToken(BaseModel):
    uid: int
    password: str
    
    
class Auth(BaseModel):
    uid: int
    token: str
    

class UpdatePerms(Auth):
    member_id: int
    perms: dict
    
    
class CWD(Auth):
    cwd: str
    
    
class Path(CWD):
    path: str
    
    
class Rename(Path):
    new_name: str
    
    
class Write(Path):
    content: str
    

class DebugIndex(Auth):
    index: int = 0
    
    
class DebugPath(Auth):
    path: str
    