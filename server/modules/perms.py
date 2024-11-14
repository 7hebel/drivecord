from modules.discord import assets

from dataclasses import dataclass, asdict
import discord


@dataclass
class DrivePermissions:
    read: bool = False
    write: bool = False
    admin: bool = False
    owner: bool = False

    def __apply_special_values(self) -> None:
        if self.owner:
            self.admin = True

        if self.admin:
            self.read = True
            self.write = True
            
        if self.write:
            self.read = True

    def __post_init__(self) -> None:
        self.__apply_special_values()

    def update(self, **kwargs) -> "DrivePermissions":
        for k, v in kwargs.items():
            self.__dict__[k] = v

        self.__apply_special_values()
        return self
    
    def export(self) -> dict[str, bool]:
        return asdict(self)
    
    @staticmethod
    def import_data(data: dict[str, bool]) -> "DrivePermissions":
        dp = DrivePermissions()
        dp.update(**data)
        return dp
    

READ_PERMS_ERROR_EMBED = discord.Embed(
    title=f"{assets.EMOJI_ACCOUNT} `READ` permissions required.",
    description="You need either `READ` or `ADMIN`"
                "permissions to perform this action.",
    color=assets.PERMS_ERROR_COLOR
)

WRITE_PERMS_ERROR_EMBED = discord.Embed(
    title=f"{assets.EMOJI_ACCOUNT} `WRITE` permissions required.",
    description="You need either `WRITE` or `ADMIN`"
                "permissions to perform this action.",
    color=assets.PERMS_ERROR_COLOR
)

ADMIN_PERMS_ERROR_EMBED = discord.Embed(
    title=f"{assets.EMOJI_ACCOUNT} `ADMIN` permissions required.",
    description="You need `ADMIN` permissions to perform this action.",
    color=assets.PERMS_ERROR_COLOR
)
