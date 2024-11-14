from modules.discord.pointers import guilds_ids_db
from modules.discord.data import DriveGuild
from modules.discord.cogs import setups
from modules.paths import sizeof_fmt
from modules.discord import assets
from modules.filesystem import fs
from modules.logs import Log
from modules import database
from modules import errors
from modules import perms

from discord.ext import commands
import discord
import base64
import json
import os


def build_error_message(command: str, description: str = "") -> discord.Embed:
    embed = discord.Embed(
        color=assets.ERROR_COLOR,
        title=f"{assets.EMOJI_ERROR} :   {command}",
        description=description
    )

    return embed


def build_output_message(command: str, result: str) -> discord.Embed:
    embed = discord.Embed(
        color=assets.PRIMARY_COLOR,
        title=f"{assets.EMOJI_CLI} :   {command}",
        description=result
    )

    return embed


def is_console_channel(ctx: commands.Context) -> bool:
    """ Check if context's channel is a guild's console channel. """
    guild = ctx.guild

    try:
        ids_reg = guilds_ids_db.get(guild.id)
    except database.KeyNotFound:
        Log.warn(f"Send command to not inialized guild: {guild.name}")
        return False

    return ctx.channel.id == ids_reg.console_id


def _build_file_edit_ui(drive_guild: DriveGuild, uid: int, file: fs.FS_File, all_content: str) -> discord.ui.View:
    page_content_size = 3800
    name = file.name
    content_pages = [all_content[i:i + page_content_size] for i in range(0, len(all_content), page_content_size)]
    if not content_pages:
        content_pages = [""]

    def build_editor_modal(index: int) -> None:
        class _EditFileModal(discord.ui.Modal, title=f"📝 Edit page: {index + 1}."):
            new_content = discord.ui.TextInput(
                label=f"File: {name} (bytes: {page_content_size*index} - {page_content_size*(index+1)})",
                required=True,
                default=content_pages[index],
                style=discord.TextStyle.long
            )

            async def on_submit(self, interaction: discord.Interaction) -> None:
                new_content = self.new_content.value
                content_pages[index] = new_content
                all_content = "".join(content_pages)

                await interaction.response.edit_message(content=f"Edited file: `{name}` at page: {index + 1}", view=None)
                await drive_guild.write_file(uid, file.path_to(), all_content)

        return _EditFileModal()


    class EditFilePageMenu(discord.ui.Select):
        def __init__(self) -> None:
            options = [
                discord.SelectOption(
                    label=f"Page {n+1}",
                    description=f"Edit content at: {page_content_size*n}b - {page_content_size*(n+1)-1}b",
                    emoji="📝",
                    value=n
                )
                for n in range(len(content_pages))
            ]
            super().__init__(placeholder="📝 Choose editor page.", options=options)

        async def callback(self, interaction: discord.Interaction) -> None:
            if interaction.user.id != uid:
                await interaction.response.send_message("You are not command author.", ephemeral=True)
                return

            page_index = int(self.values[0])
            await interaction.response.send_modal(build_editor_modal(page_index))

    view = discord.ui.View(timeout=None)
    view.add_item(EditFilePageMenu())
    return view


class BotConsoleCommands(commands.Cog):
    def __init__(self, client: discord.Client) -> None:
        self.client = client

    @commands.command(
        name="_reinit",
        help="Send DriveCord setup message which allows You to fully reinitialize server (data will be lost).",
        usage="Admin"
    )
    async def cmd_manual_reinit(self, ctx: commands.Context) -> None:
        if not is_console_channel(ctx):
            return

        manager = await DriveGuild.get(ctx.guild)
        if not manager.get_permissions(ctx.author).admin:
            return await ctx.reply(embed=perms.ADMIN_PERMS_ERROR_EMBED)

        await manager.log(f"{ctx.author.name} executed reinit command")

        await setups.setup_guild_initialization(ctx.guild)
        await ctx.reply(embed=build_output_message("_reinit", "Initialization setup message sent. (Check system channel)"))

    @commands.command(
        name="_cache",
        brief="[index: BucketNumber = 0]",
        help="Displays cache value of a bucket with given index. (channel-id: tot_size_b)",
        usage="Admin"
    )
    async def cmd_dump_cache(self, ctx: commands.Context, index: int = 0) -> None:
        if not is_console_channel(ctx):
            return

        manager = await DriveGuild.get(ctx.guild)
        if not manager.get_permissions(ctx.author).admin:
            return await ctx.reply(embed=perms.ADMIN_PERMS_ERROR_EMBED)

        bucket = manager.memory_manager.buckets.get(index)
        if bucket is None:
            await ctx.reply(embed=build_error_message(f"_cache {index}", f"`Bucket {index}` not found."), ephemeral=True)
            return

        cache_msg = json.dumps(bucket.cache, indent=2)
        await ctx.reply(embed=build_output_message(f"_cache {index}", f"`Bucket {index}` cache:\n```json\n{cache_msg}```"), ephemeral=True)

    @commands.command(
        name="_recache",
        brief="[index: BucketNumber = 0]",
        help="Recalculate cache for given bucket.",
        usage="Admin"
    )
    async def cmd_recache(self, ctx: commands.Context, index: int = 0) -> None:
        if not is_console_channel(ctx):
            return

        manager = await DriveGuild.get(ctx.guild)
        if not manager.get_permissions(ctx.author).admin:
            return await ctx.reply(embed=perms.ADMIN_PERMS_ERROR_EMBED)

        bucket = manager.memory_manager.buckets.get(index)
        if bucket is None:
            await ctx.reply(embed=build_error_message(f"_cache {index}", f"`Bucket {index}` not found."), ephemeral=True)
            return

        new_cache = await bucket._build_cache(ctx.guild, index, bucket.data_channels)
        bucket.cache = new_cache
        await bucket._save_cache()

        cache_msg = json.dumps(bucket.cache, indent=2)
        await ctx.reply(embed=build_output_message(f"_recache {index}", f"Recalculated cache for `Bucket {index}`:\n```json\n{cache_msg}```"), ephemeral=True)

    @commands.command(
        name="_trace",
        brief="<name: FileName>",
        help="Trace the route of file's content in memory. Outputs list of messages, amount of chunks and header address.",
        usage="Admin"
    )
    async def cmd_trace(self, ctx: commands.Context, name: str = None) -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        if not drive_man.get_permissions(ctx.author).admin:
            return await ctx.reply(embed=perms.ADMIN_PERMS_ERROR_EMBED)

        if name is None:
            return await ctx.reply(embed=build_error_message("_trace", "Missing `<name>` attribute! (_trace <name>)"))

        cwd, cwd_ok = await drive_man.get_cwd(ctx.author.id, ctx)
        if not cwd_ok:
            return

        for file in cwd.files:
            if file.name == name:
                break
        else:
            return await ctx.reply(embed=build_error_message(f"_trace {name}", f"File not found: `{name}`"), ephemeral=True)

        trace = await drive_man.memory_manager.get_content_trace(file.mem_addr)
        if isinstance(trace, errors.T_Error):
            return await ctx.reply(embed=build_error_message(f"_trace {name}", f"Fail: `{trace}`"), ephemeral=True)

        if not trace:
            return await ctx.reply(embed=build_error_message(f"_trace {name}", "Blank memory trace. This file is inproperly allocated and there might be some problems with it..."), ephemeral=True)

        split_urls = drive_man.memory_manager.split_content(trace, 20)
        message = await ctx.reply(embed=build_output_message(f"_trace {name}", f"**Memory trace route for file: ** `{name}`\nHeader address: `{file.mem_addr.prepare_mem_addr()}`\nTotal messages: `{len(trace)}`"), ephemeral=True)

        for urls_part in split_urls:
            urls = " -> ".join([msg.jump_url for msg in urls_part])
            await message.reply(urls)

    @commands.command(
        name="_seek",
        brief="<addr: MemoryAddress>",
        help="Check message at given memory address. <addr> format: channel-id:message-id",
        usage="Admin"
    )
    async def cmd_seekaddr(self, ctx: commands.Context, addr: str = None) -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        if not drive_man.get_permissions(ctx.author).admin:
            return await ctx.reply(embed=perms.ADMIN_PERMS_ERROR_EMBED)

        if addr is None:
            return await ctx.reply(embed=build_error_message("_seek", "Missing `<addr>` attribute! (seek <addr>)"), ephemeral=True)

        addr = addr.split(":")
        if len(addr) != 2:
            return await ctx.reply(embed=build_error_message(f"_seek {addr}", "Invalid `address` format. (`ch_id:msg_id`)"), ephemeral=True)

        address = fs.MemoryAddress(*addr)
        target = await drive_man.memory_manager.seek_addr(address)
        if target is None:
            return await ctx.reply(embed=build_error_message(f"_seek {addr}", "Invalid address."), ephemeral=True)

        await ctx.reply(embed=build_output_message(f"_seek {addr}", f"Target: {target.jump_url}"), ephemeral=True)

    @commands.command(
        name="usage",
        help="Check memory usage on this DriveCord instance."
    )
    async def cmd_memusage(self, ctx: commands.Context) -> None:
        manager = await DriveGuild.get(ctx.guild)
        usage_per_bucket = manager.memory_manager.get_memory_usage()
        total_used = sum(usage_per_bucket.values())

        message = f"**Used memory**: `{sizeof_fmt(total_used)}`\n\nUsage per bucket:\n"
        for i, mem in usage_per_bucket.items():
            percentage = 100.0
            if total_used > 0:
                percentage = round(((mem / total_used) * 100), 2)
            message += f"* data_{i}: `{sizeof_fmt(mem)}` ({percentage}%)"

        await ctx.reply(embed=build_output_message("usage", message))

    @commands.command(
        name="home",
        help="Change CWD to the base directory."
    )
    async def cmd_home(self, ctx: commands.Context) -> None:
        if not is_console_channel(ctx):
            return

        manager = await DriveGuild.get(ctx.guild)
        manager.set_cwd(ctx.author.id, fs.HOME_DIR)
        await ctx.reply(embed=build_output_message("home", f"`{fs.HOME_DIR}`"))

    @commands.command(
        name="ls",
        aliases=["dir"],
        help="Output list of directories and files (with size) in CWD."
    )
    async def cmd_listdir(self, ctx: commands.Context) -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        target, _ = await drive_man.get_cwd(ctx.author.id, ctx)
        await ctx.reply(embed=build_output_message(ctx.invoked_with, f"```asciidoc\n{target.draw_tree()}```"))

    @commands.command(
        name="cwd",
        help="Display Your current working directory path."
    )
    async def cmd_get_current_working_dir(self, ctx: commands.Context) -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        cwd, _ = await drive_man.get_cwd(ctx.author.id, ctx)
        await ctx.reply(embed=build_output_message("cwd", f"`{cwd.path_to()}`"))

    @commands.command(
        name="cd",
        brief="<path: DirPath>",
        help="Change CWD to path. Use \"..\" to move to parent directory. "
             "You can combine paths into one like: \"cd ../foo/bar\""
    )
    async def cmd_change_dir(self, ctx: commands.Context, rel_path: str = None) -> None:
        if not is_console_channel(ctx):
            return

        if rel_path is None:
            await ctx.reply(embed=build_error_message("cd", "Missing `<path>` attribute! (cd <path>)"))
            return

        drive_man = await DriveGuild.get(ctx.guild)
        cwd, cwd_ok = await drive_man.get_cwd(ctx.author.id, ctx)
        if not cwd_ok:
            return

        target = cwd.move_to(rel_path)

        if target is None:
            await ctx.reply(embed=build_error_message(f"cd {rel_path}", f"Target path doesn't exist: `{cwd.path_to()}{rel_path}`"))
            return

        if isinstance(target, fs.FS_File):
            await ctx.reply(embed=build_error_message(f"cd {rel_path}", "Cannot move to a File object."))
            return

        drive_man.set_cwd(ctx.author.id, target)

        await ctx.reply(embed=build_output_message(f"cd {rel_path}", f"`{target.path_to()}`"))

    @commands.command(
        name="mkdir",
        aliases=["mkd", "mkdir+", "mkd+"],
        brief="<path: DirPath>",
        help="Create new directory at given path. Use `+` at the end of command name to automatically change directory to the created one.",
        usage="Write"
    )
    async def cmd_mkdir(self, ctx: commands.Context, path: str = None) -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        if not drive_man.get_permissions(ctx.author).write:
            return await ctx.reply(embed=perms.WRITE_PERMS_ERROR_EMBED)

        if path is None:
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with}", "Missing `<path>` attribute! (mkdir <path>)"))

        name = os.path.basename(path)
        status = await drive_man.create_directory(ctx.author.id, path)
        if isinstance(status, errors.T_Error):
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with} {name}", f"Fail: `{status}`"))

        await ctx.reply(embed=build_output_message(f"{ctx.invoked_with} {name}", f"Created `{name}/`"))

        if ctx.invoked_with.endswith("+"):
            await self.cmd_change_dir(ctx, path)

    @commands.command(
        name="mkfile",
        aliases=["mkf", "touch"],
        brief="<path: FilePath>",
        help="Create new file at given path.",
        usage="Write"
    )
    async def cmd_mkfile(self, ctx: commands.Context, path: str = None) -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        if not drive_man.get_permissions(ctx.author).write:
            return await ctx.reply(embed=perms.WRITE_PERMS_ERROR_EMBED)

        if path is None:
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with}", "Missing `<path>` attribute! (mkfile <path>)"))

        name = os.path.basename(path)
        status = await drive_man.create_file(ctx.author.id, path)
        if isinstance(status, errors.T_Error):
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with} {name}", f"Fail: `{status}`"))

        await ctx.reply(embed=build_output_message(f"{ctx.invoked_with} {name}", f"Created `{name}`"))

    @commands.command(
        name="read",
        aliases=["cat"],
        brief="<path: FilePath>",
        help="Displays content of given file. Outputs \"(blank content)\" if file is blank.",
        usage="Read"
    )
    async def cmd_read(self, ctx: commands.Context, path: str = None) -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        if not drive_man.get_permissions(ctx.author).read:
            return await ctx.reply(embed=perms.READ_PERMS_ERROR_EMBED)

        if path is None:
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with}", "Missing `<path>` attribute! (read <path>)"))

        cwd, cwd_ok = await drive_man.get_cwd(ctx.author.id, ctx)
        if not cwd_ok:
            return
        target = cwd.move_to(path)

        content_b = await drive_man.get_file_content(ctx.author.id, path)
        if isinstance(content_b, errors.T_Error):
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with} {path}", f"Fail: `{content_b}`"))

        content = content_b.decode()
        chunks = drive_man.memory_manager.split_content(content)
        ext = target.name.split(".")[-1]

        for i, chunk in enumerate(chunks):
            await ctx.reply(embed=build_output_message(f"{ctx.invoked_with} {path}", f"({i + 1}/{len(chunks)})\n```{ext}\n{chunk}```"), ephemeral=True)

        if not chunks:
            await ctx.reply(embed=build_output_message(f"{ctx.invoked_with} {path}", "```(blank content)```"), ephemeral=True)

    @commands.command(
        name="pull",
        aliases=["download", "get"],
        brief="[name: FileName / DirName = .]",
        help="Download file or directory (as a .zip). Default target is CWD. (Up to 25Mib, bigger files can be downloaded via CLI tool)",
        usage="Read"
    )
    async def cmd_pull(self, ctx: commands.Context, path: str = ".") -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        if not drive_man.get_permissions(ctx.author).read:
            return await ctx.reply(embed=perms.READ_PERMS_ERROR_EMBED)

        file = await drive_man.pull_object(ctx.author.id, path)

        if isinstance(file, errors.T_Error):
            await ctx.reply(embed=build_error_message(f"{ctx.invoked_with} {path}", f"Fail: `{file}`"))
            return

        await ctx.reply(embed=build_output_message(f"{ctx.invoked_with} {path}", f"💾 Download `{path}`"), file=file.to_discord_file(), ephemeral=True)

    @commands.command(
        name="push",
        aliases=["upload"],
        brief="(Including Discord file in message.)",
        help="Upload file from Your local client to the CWD.",
        usage="Write"
    )
    async def cmd_push(self, ctx: commands.Context)  -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        if not drive_man.get_permissions(ctx.author).write:
            return await ctx.reply(embed=perms.WRITE_PERMS_ERROR_EMBED)

        files = ctx.message.attachments
        if not files:
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with}", "No files attached."))

        for file in files:
            name = file.filename
            content = base64.b64encode(await file.read()).decode()

            create_status = await drive_man.create_file(ctx.author.id, name)
            if isinstance(create_status, errors.T_Error):
                return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with}", f"Create-Fail: `{create_status}` ({name})"))

            write_status = await drive_man.write_file(ctx.author.id, name, content, skip_encoding=True)
            if isinstance(write_status, errors.T_Error):
                return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with}", f"Write-Fail: `{write_status}` ({name})"))

        await ctx.reply(embed=build_output_message(f"{ctx.invoked_with}", f"Uploaded {len(files)} files."))

    @commands.command(
        name="edit",
        aliases=["edt", "write"],
        brief="<path: FilePath>",
        help="Sends message with \"Open editor\" button which allows You to edit file's content in modal.",
        usage="Write"
    )
    async def cmd_edit_file(self, ctx: commands.Context, path: str = None) -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        if not drive_man.get_permissions(ctx.author).write:
            return await ctx.reply(embed=perms.WRITE_PERMS_ERROR_EMBED)

        if path is None:
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with}", "Missing `<path>` attribute! (edit <path>)"))

        cwd, cwd_ok = await drive_man.get_cwd(ctx.author.id, ctx)
        if not cwd_ok:
            return

        target = cwd.move_to(path)

        content_b = await drive_man.get_file_content(ctx.author.id, path)
        if isinstance(content_b, errors.T_Error):
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with} {path}", f"Fail: `{content_b}`"))

        content = content_b.decode()
        view = _build_file_edit_ui(drive_man, ctx.author.id, target, content)
        await ctx.reply(embed=build_output_message(f"{ctx.invoked_with} {path}", f"Edit file: `{target.name}`"), view=view, ephemeral=True)

    @commands.command(
        name="rm",
        brief="<path: FilePath or DirPath>",
        help="Remove object (file or dir) at given path. Removes directory with content inside it.",
        usage="Write"
    )
    async def cmd_rm(self, ctx: commands.Context, rm_path: str = None) -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        if not drive_man.get_permissions(ctx.author).write:
            return await ctx.reply(embed=perms.WRITE_PERMS_ERROR_EMBED)

        if rm_path is None:
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with}", "Missing `<path>` attribute! (rm <path>)"))

        status = await drive_man.delete_fs_obj(ctx.author.id, rm_path)
        if isinstance(status, errors.T_Error):
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with} {rm_path}", f"Fail: `{status}`"))

        await ctx.reply(embed=build_output_message(f"{ctx.invoked_with} {rm_path}", f"Removed `{rm_path}`"))
        await drive_man.get_cwd(ctx.author.id, ctx)  # Validate CWD.

    @commands.command(
        name="rename",
        brief="<path: FilePath or DirPath> <newName: Name>",
        aliases=["ren"],
        help="Rename object if name is available.",
        usage="Write"
    )
    async def cmd_rename(self, ctx: commands.Context, path: str = None, new_name: str = None) -> None:
        if not is_console_channel(ctx):
            return

        drive_man = await DriveGuild.get(ctx.guild)
        if not drive_man.get_permissions(ctx.author).write:
            return await ctx.reply(embed=perms.WRITE_PERMS_ERROR_EMBED)

        if path is None:
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with}", "Missing `<path>` attribute! (rename <path> <newName>)"))

        if new_name is None:
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with} {path}", "Missing `<newName>` attribute! (rename <path> <newName>)"))

        status = await drive_man.rename(ctx.author.id, path, new_name)
        if isinstance(status, errors.T_Error):
            return await ctx.reply(embed=build_error_message(f"{ctx.invoked_with} {path} {new_name}", f"Fail: `{status}`"))

        await ctx.reply(embed=build_output_message(f"{ctx.invoked_with} {path} {new_name}", "Sucessfully renamed."))


async def setup(client: discord.Client) -> None:
    await client.add_cog(BotConsoleCommands(client))
