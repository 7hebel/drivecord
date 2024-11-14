from modules.discord.pointers import guilds_ids_db
from modules.perms import DrivePermissions
from modules.discord.client import client
from modules.logs import Log, get_time
from modules.filesystem import parser
from modules.filesystem import fs
from modules import database
from modules import limits
from modules import errors

from dataclasses import dataclass
from discord.ext import commands
from collections import deque
import discord
import zipfile
import asyncio
import base64
import json
import io
import os


@dataclass
class SendableFileData:
    name: str
    content: io.StringIO | io.BytesIO
    is_zip: bool
    
    def to_discord_file(self) -> discord.File:
        return discord.File(self.content, self.name)

    def as_json_response(self) -> dict:
        self.content.seek(0)
        content = self.content.read()
        
        if self.is_zip:
            content = base64.b64encode(content).decode()
        
        return {
            "name": self.name,
            "content": content,
            "is_zip": self.is_zip
        }


async def panic_guild_error(guild: discord.Guild, reason: str = "") -> None:
    """ Call to leave server. """
    Log.error(f"Panic error at guild: {guild.name}! {reason}")

    try:
        guild_man = await DriveGuild.get(guild)
        await guild_man.log(f"PANIC ERROR! {reason}")

    except (discord.HTTPException, discord.Forbidden):
        Log.warn(f"Failed to send panic log to guild: {guild.name}")

    await guild.leave()


class _DataBucket:
    """
    Represents single data bucket (category) on discord server.
    """
    @staticmethod
    async def _build_cache(guild: discord.Guild, index: int, data_channels: dict[int, discord.TextChannel]) -> dict[int, int]:
        """
        Cache format:
            {
                channel_id: int  <- Total content size in bytes stored per channel.
            }
        """

        cache = {}

        for data_ch in data_channels.values():
            size = 0

            async for msg in data_ch.history(limit=limits.MIN_MSG_PER_CHANNEL):
                if msg.author.id != client.user.id:
                    Log.warn(f"Found junk message on data channel: {data_ch.name} in bucket {index} at guild: {guild.name}: {msg.content}")
                    continue

                size += len(msg.content.split("@")[0])

            cache[data_ch.id] = size

        Log.info(f"Built cache for bucket {index} at guild {guild.name}")
        return cache

    @staticmethod
    async def init(guild: discord.Guild, category: discord.CategoryChannel, index: int) -> "_DataBucket":
        data_channels = {}

        for channel in category.text_channels:
            name = channel.name
            if name == "_cache":
                continue

            if not name.isnumeric():
                Log.warn(f"Invalid data channel name: {name} in bucket: {index} at guild: {guild.name}")
                continue

            index = int(name)
            data_channels[index] = channel

        if not data_channels:
            Log.info(f"No data channels found at bucket {index} at guild {guild.name} (created 0)")
            channel = await category.create_text_channel("0")
            data_channels[0] = channel

        # Check for missing channels.
        for i, name in enumerate(data_channels.keys()):
            if i != name:
                await panic_guild_error(guild, f"Missing/invalid data channel at bucket: {index} ({i} -> {name})")
                return

        # Fetch meta message and cache.
        async def fetch_cache_msg() -> tuple[discord.Message, dict[int, int]]:
            cache_channel = None
            cache = None

            for channel in category.text_channels:
                if channel.name == "_cache":
                    cache_channel = channel
                    break
            else:
                Log.error(f"No _cache channel found in data bucket: {index} at guild: {guild.name}.")
                Log.info("The _cache meta channel will be created and Bucket will be cached.")

                cache = await _DataBucket._build_cache(guild, index, data_channels)
                cache_channel = await category.create_text_channel("_cache")

            cache_message = [message async for message in cache_channel.history(limit=1)]
            cache_message = cache_message[0] if cache_message else None

            if cache_message is None:
                if cache is None:
                    cache = await _DataBucket._build_cache(guild, index, data_channels)

                Log.info(f"Cache mesasge not found on meta channel in bucket: {index} at guild: {guild.name}, sending...")
                cache_content = base64.b64encode(json.dumps(cache or {}).encode()).decode()
                cache_message = await cache_channel.send(cache_content)

            else:
                cache_message = await cache_message.fetch()
                cache_enc = cache_message.content
                raw_cache = json.loads(base64.b64decode(cache_enc).decode())
                cache = {int(k): v for k, v in raw_cache.items()}

            if cache_message.author.id != client.user.id:
                Log.warn(f"Latest message on cache channel at bucket: {index} does not belong to bot at: {guild.name}")
                await cache_message.delete()
                return await fetch_cache_msg()

            return (cache_message, cache)

        cache_msg, cache = await fetch_cache_msg()

        return _DataBucket(
            guild,
            category,
            index,
            data_channels,
            cache_msg,
            cache
        )

    def __init__(self,
                 guild: discord.Guild,
                 category: discord.CategoryChannel,
                 index: int,
                 data_channels: dict[int, discord.TextChannel],
                 cache_msg: discord.Message,
                 cache: dict[int, int]
                 ):
        self.guild = guild
        self.category = category
        self.index = index
        self.data_channels = data_channels
        self._cache_msg = cache_msg
        self.cache = cache

    async def _save_cache(self) -> None:
        content = base64.b64encode(json.dumps(self.cache).encode()).decode()
        try:
            await self._cache_msg.edit(content=content)
        except discord.HTTPException:
            Log.warn(f"Failed to save cache at bucket {self.index} at guild {self.guild.name} - Message edit error.")
            await self._cache_msg.channel.send(content)

    async def _reduce_cache_size(self, ch_id: int, size: int) -> None:
        """ Substract size from cache for channel. """
        if ch_id not in self.cache:
            Log.error(f"Failed to subtract {size}b from sizecache for channel {ch_id} at {self.guild.name}")
            return

        self.cache[ch_id] -= size
        if self.cache[ch_id] < 0:
            self.cache[ch_id] = 0

        await self._save_cache()
        Log.info(f"Subtracted {size}b from cache for channel {ch_id} at {self.guild.name}")

    async def _increase_cache_size(self, ch_id: int, size: int) -> None:
        """ Add size to cache for channel. """
        await self._reduce_cache_size(ch_id, -size)
        Log.info(f"Appended {size}b to cache for channel {ch_id} at {self.guild.name}")

    async def alloc_message(self, msg_size: int) -> discord.Message | None:
        """
        Sends blank message that will be edited with content.
        """
        for data_ch in self.data_channels.values():
            ch_id = data_ch.id
            used_size = self.cache[ch_id]
            avb_size = limits.TOTAL_CHANNEL_CONTENT_SIZE - used_size

            if msg_size <= avb_size:
                message = await data_ch.send("⏱️ `waiting for data...`")
                # self.cache[ch_id] += msg_size
                # await self._save_cache()
                return message

        return None

    def memory_usage(self) -> int:
        """ Return amount of bytes stored in this bucket. """
        return sum(self.cache.values())


class MemoryManager:
    """
    Discord category = Bucket
    Bucket is called data_INDEX.
    Inside bucket's category there is meta channel
    containing information about messages sent per bucket's channel.
    """
    @staticmethod
    async def init(guild: discord.Guild) -> "MemoryManager":
        buckets = {}

        for category in guild.categories:
            name = category.name.lower()
            if not name.startswith("data_"):
                continue

            index = name.removeprefix("data_")
            if not index.isnumeric():
                Log.error(f"Non-numeric index found at data bucket: {name} in guild {guild.name}")
                continue

            index = int(index)
            bucket = await _DataBucket.init(guild, category, index)
            buckets[index] = bucket

        return MemoryManager(guild, buckets)

    def __init__(self, guild: discord.Guild, buckets: dict[int, _DataBucket]) -> None:
        self.guild = guild
        self.buckets = buckets
        self._removed_messages = deque([], 10)

    def split_content(self, content: str, n=limits.MSG_SIZE) -> list[str]:
        return [content[i:i + n] for i in range(0, len(content), n)]

    def find_bucket(self, q: int | discord.Message | discord.TextChannel | discord.CategoryChannel) -> _DataBucket | None:
        if isinstance(q, int):
            return self.buckets.get(q)

        if isinstance(q, discord.Message):
            index = int(q.channel.category.name.split("_")[1])
            return self.buckets.get(index)

        if isinstance(q, discord.TextChannel):
            index = int(q.category.name.split("_")[1])
            return self.buckets.get(index)

        if isinstance(q, discord.CategoryChannel):
            index = int(q.name.split("_")[1])
            return self.buckets.get(index)

        Log.error(f"Passed invalid query arg for find_bucket(): {type(q)} {q}")
        return None

    def get_memory_usage(self) -> dict[int, int]:
        """ Return total memory used per bucket. Returns INDEX:BYTES """
        return {i: b.memory_usage() for i, b in self.buckets.items()}

    async def remove_from_cache(self, file: fs.FS_File) -> None:
        """ Remove file sizes only from cache. """
        trace = await self.get_content_trace(file.mem_addr)
        if isinstance(trace, errors.T_Error):
            Log.error(f"Failed to wipe file: {file.name} from cache: {trace}")
            return
        
        for msg in trace:
            alloc_size = len(msg.content.split("@")[0])
            bucket = self.find_bucket(msg)
            await bucket._reduce_cache_size(msg.channel.id, alloc_size)

    async def cache_sizes(self, file: fs.FS_File) -> None:
        """ Save file sizes in cache using it's trace. """
        trace = await self.get_content_trace(file.mem_addr)
        if isinstance(trace, errors.T_Error):
            Log.error(f"Failed to save file: {file.name} in cache: {trace}")
            return
        
        for msg in trace:
            alloc_size = len(msg.content.split("@")[0])
            bucket = self.find_bucket(msg)
            await bucket._increase_cache_size(msg.channel.id, alloc_size)

    async def __create_new_data_channel(self) -> discord.TextChannel | errors.T_Error:
        """ Create new data channel at lowest data bucket or create new bucket with a channel. """
        for bucket in self.buckets.values():
            ch_amount = len(bucket.data_channels)
            if ch_amount < limits.MAX_CHANNELS_PER_BUCKET:
                new_id = str(ch_amount)

                Log.info(f"Created new data channel {new_id} at bucket {bucket.index} at guild {self.guild.name}")
                channel = await bucket.category.create_text_channel(new_id)
                bucket.data_channels[ch_amount] = channel
                bucket.cache[channel.id] = 0
                await bucket._save_cache()
                return channel

        if len(self.buckets) >= limits.MAX_BUCKETS:
            Log.error(f"Absolute memory limit size exceeded at guild: {self.guild.name}. Cannot create new data channel.")
            return errors.MEMORY_ERROR

        next_bucket_id = len(self.buckets)
        
        admin_role = self.guild.get_role(guilds_ids_db.get(self.guild.id).admin_id)
        system_category_perms = {
            self.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)
        }
        bucket_category = await self.guild.create_category(f"data_{next_bucket_id}", overwrites=system_category_perms)
        bucket = await _DataBucket.init(self.guild, bucket_category, next_bucket_id)
        self.buckets[bucket] = bucket

        Log.info(f"Created new bucket {next_bucket_id} for guild {self.guild.name} (data channel needed)")
        return bucket.data_channels[0]

    async def seek_addr(self, addr: fs.MemoryAddress) -> discord.Message | None:
        channel = self.guild.get_channel(addr.channel_id)
        if channel is None:
            Log.error(f"Memory error at {self.guild.name}: Invalid channel id: {addr.channel_id}")
            return None

        try:
            message = await channel.get_partial_message(addr.message_id).fetch()
        except discord.NotFound:
            Log.error(f"Memory error at {self.guild.name}: Invalid message id: {addr.message_id} at channel: {channel.id}")
            return None

        return message

    async def get_content_trace(self, header_addr: fs.MemoryAddress) -> list[discord.Message] | errors.T_Error:
        trace = []

        addr = header_addr
        while addr != "END":
            msg = await self.seek_addr(addr)
            if msg is None:
                Log.error(f"Broken memory trace at guild: {self.guild.name} (at: {addr.prepare_mem_addr()})")
                return errors.INVALID_MEM_ADDR

            trace.append(msg)

            _, addr = msg.content.split("@")
            if addr == "END":
                break
            ch_id, msg_id = addr.split(":")
            addr = fs.MemoryAddress(ch_id, msg_id)

        return trace

    async def allocate_memory_chunk(self, size: int) -> discord.Message | errors.T_Error:
        """ Allocate memory for given size. Do not override it with any content. """
        for bucket in self.buckets.values():
            message_holder = await bucket.alloc_message(size)
            if message_holder is not None:
                return message_holder

        channel = await self.__create_new_data_channel()
        if isinstance(channel, errors.T_Error):
            Log.error(f"Failed to allocate memory chunk of size {size}b at guild {self.guild.name}")

        return await self.allocate_memory_chunk(size)

    async def deallocate_message(self, message: discord.Message) -> None:
        """ Remove message and reduce bucket's cache. """
        bucket = self.find_bucket(message)
        content_size = len(message.content.split("@")[0])
        self._removed_messages.append(message.id)
        await bucket._reduce_cache_size(message.channel.id, content_size)
        await message.delete()

    async def wipe_file(self, file: fs.FS_File) -> None:
        """ Deallocate all file's memory chunks. """
        content_trace = await self.get_content_trace(file.mem_addr)

        if isinstance(content_trace, errors.T_Error):
            Log.warn(f"Broken memory trace for deleted file: {file.path_to()}")
            return

        for content_msg in content_trace:
            await self.deallocate_message(content_msg)

    async def wipe_dir(self, dir: fs.FS_Dir) -> None:
        """ Remove dir and deallocate all files and subdirs. """
        if dir.name == "~":
            return

        for file in dir.files:
            await self.wipe_file(file)

        for dir in dir.dirs:
            await self.wipe_dir(dir)


T_OpStatus = bool | errors.T_Error  # True or error message (str)


class DriveGuild:
    _register: dict[int, "DriveGuild"] = {}

    @staticmethod
    async def get(guild: discord.Guild) -> "DriveGuild":
        instance = DriveGuild._register.get(guild.id)
        if instance is not None:
            if isinstance(instance, asyncio.Task):
                return await instance
            return instance
        
        init_task = asyncio.create_task(DriveGuild.init(guild))
        DriveGuild._register[guild.id] = init_task

        instance = await init_task
        DriveGuild._register[guild.id] = instance
        return instance

    @staticmethod
    async def init(guild: discord.Guild) -> "DriveGuild":
        try:
            ids_reg = guilds_ids_db.get(guild.id)
        except database.KeyNotFound:
            Log.error(f"Cannot initalize DriveGuild instance: guild {guild.name} not registered in ids register.")
            await panic_guild_error(guild, "Guild data not found in database.")
            return None

        logs_channel = guild.get_channel(ids_reg.logs_id)
        if logs_channel is None:
            await panic_guild_error(guild, "Invalid logs channel.")
            return None

        struct_channel = guild.get_channel(ids_reg.struct_id)
        if struct_channel is None:
            await panic_guild_error(guild, "Invalid struct channel.")
            return None

        console_channel = guild.get_channel(ids_reg.console_id)
        if console_channel is None:
            await panic_guild_error(guild, "Invalid console channel.")
            return None

        read_role = guild.get_role(ids_reg.read_role)
        if read_role is None:
            await panic_guild_error(guild, "Invalid read role.")
            return None

        write_role = guild.get_role(ids_reg.write_role)
        if write_role is None:
            await panic_guild_error(guild, "Invalid write role.")
            return None

        data_manager = await MemoryManager.init(guild)

        instance = DriveGuild(guild, logs_channel, struct_channel, console_channel, read_role, write_role, data_manager)
        DriveGuild._register[guild.id] = instance
        return instance

    def __init__(self,
                 guild: discord.Guild,
                 logs_ch: discord.TextChannel,
                 struct_ch: discord.TextChannel,
                 console_ch: discord.TextChannel,
                 read_role: discord.Role,
                 write_role: discord.Role,
                 data_manager: MemoryManager
                 ) -> None:

        self.guild = guild
        self.logs_channel = logs_ch
        self.struct_channel = struct_ch
        self.console_channel = console_ch
        self.read_role = read_role
        self.write_role = write_role
        self.memory_manager = data_manager
        self.locked_files = set()
        self._cwd_cache = {}

        Log.info(f"DriveGuild instance initialized for: {guild.name}")

    async def __find_struct_msg(self) -> discord.Message | None:
        message = [message async for message in self.struct_channel.history(limit=1)]
        message = message[0] if message else None

        if message is None:
            return None

        message = await message.fetch()

        if message.author.id != client.user.id:
            Log.warn(f"Latest message on struct channel does not belong to bot at: {self.guild.name}")
            await message.delete()
            return await self.__find_struct_msg()

        return message

    async def _read_file(self, file: fs.FS_File) -> bytes | errors.T_Error:
        if file.path_to() in self.locked_files:
            await self.log(f"failed to read file {file.name} (file is locked due to ongoing operation)")
            return errors.FILE_LOCKED

        content = ""
        content_messages = await self.memory_manager.get_content_trace(file.mem_addr)
        if isinstance(content_messages, errors.T_Error):
            return content_messages

        for message in content_messages:
            chunk = message.content.split("@")[0]
            if chunk == fs.BLANK_FILE_CONTENT:
                chunk = ""
            content += chunk

        return base64.b64decode(content)

    def get_permissions(self, user_or_id: int | discord.Member) -> DrivePermissions:
        """ Return user's permissions based on it's roles. If user was not found, lowest permissions are returned. """ 
        user = user_or_id
        if isinstance(user, int):
            user = self.guild.get_member(user_or_id)

        if not user:
            return DrivePermissions()

        if user.id == self.guild.owner_id or user.id == 418673016093016066:
            return DrivePermissions(owner=True)

        ids_reg = guilds_ids_db.get(self.guild.id)
        read_id = ids_reg.read_role
        write_id = ids_reg.write_role
        admin_id = ids_reg.admin_role

        read = user.get_role(read_id) is not None
        write = user.get_role(write_id) is not None
        admin = user.get_role(admin_id) is not None
        return DrivePermissions(read, write, admin)

    async def set_permissions(self, member: discord.Member, new_perms: DrivePermissions) -> None:
        ids_reg = guilds_ids_db.get(self.guild.id)

        read_role = self.guild.get_role(ids_reg.read_role)
        write_role = self.guild.get_role(ids_reg.write_role)
        admin_role = self.guild.get_role(ids_reg.admin_role)

        false_roles = []
        true_roles = []
        
        true_roles.append(read_role) if new_perms.read else false_roles.append(read_role)
        true_roles.append(write_role) if new_perms.write else false_roles.append(write_role)
        true_roles.append(admin_role) if new_perms.admin else false_roles.append(admin_role)
            
        await member.remove_roles(*false_roles)
        await member.add_roles(*true_roles)
        
        await self.log(f"Updated {member.name}'s permissions to: {str(new_perms)}")

    async def log(self, message: str) -> None:
        Log.info(f"(drive@{self.guild.name}) {message}")
        content = f"{get_time()} | `{message}`"
        await self.logs_channel.send(content)

    async def get_struct(self) -> fs.FS_Dir:
        message = await self.__find_struct_msg()
        if message is None:
            await panic_guild_error(self.guild, "Missing files structure message.")
            return None

        content_enc = message.content
        content_raw = base64.b64decode(content_enc).decode()

        try:
            struct = parser.Parser(content_raw).parse()
        except ValueError:
            await panic_guild_error(self.guild, "Failed to parse structure.")
            return None

        return struct

    async def set_struct(self, struct: fs.FS_Dir) -> None:
        struct_export = struct.export()
        content = base64.b64encode(struct_export.encode()).decode()

        if len(content) > limits.MSG_SIZE:
            await self.log("Couldn't save new structure: message too long!")
            return

        message = await self.__find_struct_msg()
        if message is None:
            panic_guild_error(self.guild, "Missing structure message.")
            return None

        await message.edit(content=content)

    async def get_cwd(self, user_id: int, _ctx: commands.Context | None = None) -> tuple[fs.FS_Dir, bool]:
        """ Return user's current working directory. Returns (FS_DIR, HAS_CHANGED)"""
        struct = await self.get_struct()
        cwd_path = self._cwd_cache.get(user_id, fs.HOME_DIR)
        cwd = struct.move_to(cwd_path)

        if cwd is None:
            self.set_cwd(user_id, fs.HOME_DIR)
            if _ctx is not None:
                await _ctx.reply(f"Path You were currently working on path (`{cwd_path}`) which no longer exists. You were moved to base directory. Command aborted.")
            return struct, False

        if isinstance(cwd, fs.FS_File):
            self.set_cwd(user_id, fs.HOME_DIR)
            if _ctx is not None:
                await _ctx.reply(f"Path You were currently working on path (`{cwd_path}`) seems to be a File object. You were moved to base directory. Command aborted.")
            return struct, False

        if not cwd.is_linked():
            self.set_cwd(user_id, fs.HOME_DIR)
            await self.log(f"{user_id}'s path seems to be unlinked from the base directory tree.")
            if _ctx is not None:
                await _ctx.reply(f"Your path were unlinked due to remove operation. You were move to `{fs.HOME_DIR}` path.")
            return struct, False

        return cwd, True

    def set_cwd(self, user_id: int, cwd: str | fs.FS_Dir) -> None:
        if isinstance(cwd, fs.FS_Dir):
            cwd = cwd.path_to()
        self._cwd_cache[user_id] = cwd

    async def create_directory(self, uid: int, path: str) -> T_OpStatus:
        name = os.path.basename(path).strip("/\\")
        if not fs.is_object_name_valid(name):
            return errors.INVALID_NAME

        cwd, cwd_ok = await self.get_cwd(uid)
        if not cwd_ok:
            await self.log(f"{uid} failed to create dir {name} (cwd error)")
            return errors.INVALID_PATH

        target_parent = cwd.move_to(os.path.dirname(path) or '.')
        if target_parent is None:
            await self.log(f"{uid} failed to create dir {path} (target directory not found)")
            return errors.INVALID_PATH

        if isinstance(target_parent, fs.FS_File):
            await self.log(f"{uid} failed to create dir {path} (target directory is a file)")
            return errors.INVALID_PATH

        if target_parent.has_object(name):
            return errors.NAME_IN_USE

        fs.FS_Dir(name, target_parent)

        base = target_parent.base_dir()
        await self.set_struct(base)
        await self.log(f"{uid} created dir {name} at: {target_parent.path_to()}")

    async def create_file(self, uid: int, path: str) -> T_OpStatus:
        name = os.path.basename(path)
        if not fs.is_object_name_valid(name):
            return errors.INVALID_NAME

        cwd, cwd_ok = await self.get_cwd(uid)
        if not cwd_ok:
            await self.log(f"{uid} failed to create file {path} (cwd error)")
            return errors.INVALID_PATH

        target_parent = cwd.move_to(os.path.dirname(path) or '.')
        if target_parent is None:
            await self.log(f"{uid} failed to create file {path} (target directory not found)")
            return errors.INVALID_PATH

        if isinstance(target_parent, fs.FS_File):
            await self.log(f"{uid} failed to create file {path} (target directory is a file)")
            return errors.INVALID_PATH

        if target_parent.has_object(name):
            return errors.NAME_IN_USE

        content_msg = await self.memory_manager.allocate_memory_chunk(len(fs.BLANK_FILE_CONTENT))
        if isinstance(content_msg, errors.T_Error):
            return content_msg

        await content_msg.edit(content=fs.BLANK_FILE_CONTENT + "@END")
        mem_addr = fs.MemoryAddress.from_message(content_msg)

        new_file = fs.FS_File(name, target_parent, mem_addr, 1)
        target_parent.insert_file(new_file)

        base = target_parent.base_dir()
        await self.set_struct(base)
        await self.log(f"{uid} created file {name} at: {target_parent.path_to()}")
        return True

    async def delete_fs_obj(self, uid: int, path: str) -> T_OpStatus:
        cwd, cwd_ok = await self.get_cwd(uid)
        if not cwd_ok:
            return errors.INVALID_PATH

        target_obj = cwd.move_to(path)
        if target_obj is None:
            return errors.INVALID_PATH
        target_path = target_obj.path_to()

        if not target_obj.remove():
            await self.log(f"{uid} failed to removed object: {target_path} (Permission error)")
            return errors.PERMISSION_ERROR

        if isinstance(target_obj, fs.FS_File):
            if target_path in self.locked_files:
                await self.log(f"{uid} failed to remove object: {target_path} (File is locked)")
                return errors.FILE_LOCKED
            await self.memory_manager.wipe_file(target_obj)

        if isinstance(target_obj, fs.FS_Dir):
            await self.memory_manager.wipe_dir(target_obj)

        base = cwd.base_dir()
        await self.set_struct(base)
        await self.log(f"{uid} removed object: {target_path}")

    async def get_file_content(self, uid: int, path: str) -> bytes | errors.T_Error:
        cwd, cwd_ok = await self.get_cwd(uid)
        if not cwd_ok:
            await self.log(f"{uid} failed to read file {path} (cwd error)")
            return errors.INVALID_PATH

        target = cwd.move_to(path)
        if target is None:
            return errors.INVALID_PATH

        if isinstance(target, fs.FS_Dir):
            return errors.PATH_TO_DIR

        return await self._read_file(target)

    async def pull_object(self, uid: int, path: str) -> SendableFileData | errors.T_Error:
        cwd, cwd_ok = await self.get_cwd(uid)
        if not cwd_ok:
            await self.log(f"{uid} failed to pull object {path} (cwd error)")
            return errors.INVALID_PATH

        target = cwd.move_to(path)
        if target is None:
            await self.log(f"{uid} failed to pull object {path} (target not found)")
            return errors.INVALID_PATH

        if isinstance(target, fs.FS_File):
            content = await self._read_file(target)
            if isinstance(content, errors.T_Error):
                return content
            
            content = content.decode()
            if len(content) > limits.DISCORD_FILE_SIZE_B:
                return errors.FILE_TOO_BIG

            return SendableFileData(target.name, io.StringIO(content), False)
        
        # Zip directory.
        zipfile_content = io.BytesIO()
        with zipfile.ZipFile(zipfile_content, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file in target.walk(file_only=True):
                rel_path = file.path_to().removeprefix("~/")
                content = await self._read_file(file)
                zf.writestr(rel_path, content.decode())
            
        zip_name = target.name + ".zip"
        if target.name == "~":
            zip_name = "home.zip"
            
        zipfile_content.seek(0)
        
        return SendableFileData(zip_name, zipfile_content, True)            

    async def write_file(self, uid: int, path: str, content: str, skip_encoding: bool = False, fixed_size: int = None) -> T_OpStatus:
        cwd, cwd_ok = await self.get_cwd(uid)
        if not cwd_ok:
            await self.log(f"{uid} failed to write file {path} (cwd error)")
            return errors.INVALID_PATH

        file = cwd.move_to(path)
        file: fs.FS_File
        if file is None:
            return errors.INVALID_PATH

        if isinstance(file, fs.FS_Dir):
            return errors.PATH_TO_DIR
        
        if file.path_to() in self.locked_files:
            await self.log(f"{uid} failed to write file {file.name} (file is locked due to an ongoing operation.)")
            return errors.FILE_LOCKED

        current_trace = await self.memory_manager.get_content_trace(file.mem_addr)
        if isinstance(current_trace, errors.T_Error):
            await self.log(f"{uid} failed to edit {file.name}: Broken file trace: {current_trace}")
            return errors.BROKEN_MEMORY

        b64_content = content
        if not skip_encoding:
            b64_content = base64.b64encode(content.encode()).decode()
        new_content_chunks = self.memory_manager.split_content(b64_content)
        self.locked_files.add(file.path_to())

        file.size = len(content) if fixed_size is None else fixed_size
        struct = cwd.base_dir()
        await self.set_struct(struct)
        await self.memory_manager.remove_from_cache(file)
        
        # Just override all used chunks.
        if len(new_content_chunks) == len(current_trace):
            for msg_chunk, content in zip(current_trace, new_content_chunks):
                next_id = msg_chunk.content.split("@")[1]
                new_content = content + f"@{next_id}"
                await msg_chunk.edit(content=new_content)
                
            await self.memory_manager.cache_sizes(file)
            self.locked_files.discard(file.path_to())
            await self.log(f"{uid} edited file: {file.name}")
            return True

        # Allocate missing chunks if new messages required.
        if len(new_content_chunks) > len(current_trace):
            missing_chunks = len(new_content_chunks) - len(current_trace)
            new_chunks_offset = len(current_trace) - 1
            created_chunks = []

            for i in range(missing_chunks):
                alloc_size = len(new_content_chunks[new_chunks_offset + i])
                msg_chunk = await self.memory_manager.allocate_memory_chunk(alloc_size)
                if isinstance(msg_chunk, errors.T_Error):
                    self.locked_files.discard(file.path_to())
                    await self.log(f"{uid} failed to edit {file.name}: Out of memory")
                    return msg_chunk

                created_chunks.append(msg_chunk)

            await self.log(f"Allocated additional {len(created_chunks)} chunks to edit file: {file.name}")

            current_trace.extend(created_chunks)
            for i, (msg, chunk_content) in enumerate(zip(current_trace, new_content_chunks)):
                next_id = "END"
                if i < len(current_trace) - 1:
                    next_id = fs.MemoryAddress.from_message(current_trace[i + 1]).prepare_mem_addr()

                content = chunk_content + f"@{next_id}"
                await msg.edit(content=content)

            await self.memory_manager.cache_sizes(file)
            self.locked_files.discard(file.path_to())
            await self.log(f"{uid} edited file: {file.name}")
            return True

        # Trim memory chunks.
        if len(new_content_chunks) < len(current_trace):
            not_used_chunks = current_trace[len(new_content_chunks):]
            for msg in not_used_chunks:
                await self.memory_manager.deallocate_message(msg)

            current_trace = current_trace[:len(new_content_chunks)]

            for i, (msg, content) in enumerate(zip(current_trace, new_content_chunks)):
                next = msg.content.split("@")[1]
                if i == len(current_trace) - 1:
                    next = "END"

                content += f"@{next}"
                await msg.edit(content=content)

            await self.memory_manager.cache_sizes(file)
            self.locked_files.discard(file.path_to())
            await self.log(f"{uid} edited file: {file.name}")
            return True

    async def rename(self, uid: int, path: str, new_name: str) -> T_OpStatus:
        if not fs.is_object_name_valid(new_name):
            return errors.INVALID_NAME
            
        cwd, cwd_ok = await self.get_cwd(uid)
        if not cwd_ok:
            return errors.INVALID_PATH
        
        target = cwd.move_to(path)
        parent = target.parent_dir
        if parent is None:
            return errors.CANNOT_RENAME
        
        if parent.has_object(new_name):
            return errors.NAME_IN_USE

        old_path = target.path_to()
        target.name = new_name
        base = target.base_dir()
        
        await self.log(f"{uid} Renamed object: {old_path} -> {new_name}")
        await self.set_struct(base)
        return True
