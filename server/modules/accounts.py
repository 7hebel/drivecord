from modules.discord import pointers
from modules.discord import client
from modules import timestamp
from modules.logs import Log
from modules import database
from modules import limits
from modules import errors

import hashlib
import bcrypt


def hash_ip(ip_addr: str) -> str:
    return hashlib.sha256(ip_addr.encode()).hexdigest()


@database.DBModel.model("access_tokens", "!token_id")
class AccessToken:
    token_id: str
    owner: int
    ip_address: str
    date_created: int
    
    @staticmethod
    def get_user_tokens(uid: int) -> list["AccessToken"]:
        user_tokens = []
        for token in access_tokens_db.get_all_models():
            if token.owner == uid:
                user_tokens.append(token)
                
        return user_tokens
    
    @staticmethod
    def new_token(uid: int, ip_addr: str) -> "AccessToken":
        salt = bcrypt.gensalt().decode()
        time = timestamp.generate_timestamp()
        token_id = hashlib.sha256(f"{uid}{ip_addr}{time}{salt}".encode()).hexdigest()
        
        token = AccessToken(
            token_id, uid, ip_addr, time
        )
        
        access_tokens_db.insert(token)
        Log.info(f"Generated new access token for: {uid}")
        
        return token
    
    @property
    def masked(self) -> str:
        """ Returns masked, public version of access token. """
        return self.token_id[:5]


@database.DBModel.model("users", "!discord_id")
class User:
    discord_id: int
    password: str
    date_join: int
    servers_ids: list = database.NOT_REQUIRED
    is_banned: bool = False
    
    @staticmethod
    def register(discord_id: int, password: str) -> "User":
        if str(discord_id) in users_db.get_all_keys():
            Log.error(f"Already registerd user tried to register: {discord_id}")
            return errors.ACCOUNT_ALREADY_REGISTERED

        servers_ids = []
        for guild_data in pointers.guilds_ids_db.get_all_models():
            guild = client.client.get_guild(guild_data.guild_id)
            if guild is None:
                continue
            
            if discord_id in guild._members:
                servers_ids.append(guild.id)

        user_model = User(
            discord_id=discord_id,
            password=password,
            date_join=timestamp.generate_timestamp(),
            servers_ids=servers_ids,
            is_banned=False
        )

        Log.info(f"Registered account via Discord modal: {discord_id}")
        return users_db.insert(user_model)

    @staticmethod
    def get_by_uid(uid: int) -> "User | None":
        for user in users_db.get_all_models():
            if user.discord_id == uid:
                return user

    def __post_init__(self) -> None:
        self.access_tokens = AccessToken.get_user_tokens(self.discord_id)

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password.encode())

    def request_access_token(self, password: str, ip_addr: str) -> AccessToken | errors.T_Error:
        if not bcrypt.checkpw(password.encode(), self.password.encode()):
            return errors.INVALID_PASSWORD
        
        ip_addr = hash_ip(ip_addr)
        
        for token in self.access_tokens:
            if token.ip_address == ip_addr:
                return token
        
        if len(self.access_tokens) >= limits.MAX_ACCESS_TOKENS:
            return errors.MAX_ACCESS_TOKENS
        
        return AccessToken.new_token(self.discord_id, ip_addr)
    
    def check_access_token(self, token_id: str, ip_addr: str) -> bool:
        for token in self.access_tokens:
            if token.token_id == token_id:
                break
        else:
            Log.warn(f"Checking access token for: {self.discord_id} failed: Invalid token_id: {token_id}")
            return False
        
        if token.ip_address != hash_ip(ip_addr):
            Log.warn(f"Checking access token for: {self.discord_id} failed: Invalid IP Adress.")
            return False
        
        return True
        
    def burn_access_token(self, token_id: str) -> None:
        try:
            token = access_tokens_db.get(token_id)
        except database.KeyNotFound:
            return Log.error(f"Failed to burn token: {token_id} for: {self.discord_id} (token not found in DB)")
            
        if token.owner != self.discord_id:
            return Log.error(f"Failed to burn token: {token_id} for: {self.discord_id} (token is not owned by this user but {token.owner})")
            
        access_tokens_db.delete(token_id)
        if token in self.access_tokens:
            self.access_tokens.remove(token)
        
        Log.info(f"Burned token: {token_id} for: {self.discord_id}")
        
    def assign_instance(self, gid: int) -> None:
        if gid not in self.servers_ids:
            self.servers_ids.append(gid)
            users_db.update(self.discord_id, {"servers_ids": gid}, iter_append=True)
        
    def remove_instance(self, gid: int) -> None:
        if gid in self.servers_ids:
            self.servers_ids.remove(gid)
            users_db.update(self.discord_id, {"servers_ids": gid}, iter_pop=True)
            
    def get_instances(self) -> dict[int, str]:
        instances = {}
        
        for server_id in self.servers_ids:
            guild = client.client.get_guild(server_id)
            if guild is None:
                Log.error(f"Found invalid guild: {server_id} in user's instances: {self.discord_id}")
                self.remove_instance(server_id)
                continue
            
            instances[server_id] = guild.name
            
        return instances
                

users_db = database.Database[User](User)
access_tokens_db = database.Database[AccessToken](AccessToken)
