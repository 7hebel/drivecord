from dataclasses import dataclass, asdict
from enum import Enum


class PermissionType(Enum):
    READ = "Read"
    WRITE = "Write"
    ADMIN = "Admin"
    OWNER = "Owner"
    
    @staticmethod
    def from_drive_perms(perms: "DrivePermissions") -> "PermissionType":
        if perms.owner:
            return PermissionType.OWNER
        if perms.admin:
            return PermissionType.ADMIN
        if perms.write:
            return PermissionType.WRITE
        return PermissionType.READ
    
    @staticmethod
    def has_perms(user_perms: "PermissionType", required_perms: "PermissionType | None") -> bool:
        if required_perms is None:
            return True
        if user_perms == PermissionType.OWNER:
            return True
        if user_perms == PermissionType.ADMIN:
            return not required_perms == PermissionType.OWNER
        if user_perms == PermissionType.WRITE:
            return required_perms in (PermissionType.READ, PermissionType.WRITE)
        return required_perms == PermissionType.READ
       
       
@dataclass
class DrivePermissions:
    read: bool = False
    write: bool = False
    admin: bool = False
    owner: bool = False
    
    @staticmethod
    def from_data(data: dict[str, bool]) -> "DrivePermissions":
        instance = DrivePermissions()
        
        for k, v in data.items():
            if k in instance.__dict__:
                setattr(instance, k, v)
                
        return instance
        
    def export(self) -> dict[str, bool]:
        return asdict(self)
        