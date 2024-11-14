from modules.discord.pointers import guilds_ids_db
from modules.discord.cogs import console, setups
from modules.discord import assets
from modules.discord import data
from modules.logs import Log
from modules import accounts

from discord.ext import commands
import discord


class BotEvents(commands.Cog):
    def __init__(self, client: discord.Client) -> None:
        self.client = client

    async def _is_crucial_channel(self, channel: discord.TextChannel) -> bool:
        if str(channel.guild.id) not in guilds_ids_db.get_all_keys():
            return False
        
        manager = await data.DriveGuild.get(channel.guild)
        
        if channel.id in (manager.logs_channel.id, manager.struct_channel.id, manager.console_channel.id, manager.logs_channel.category_id):
            return True
        
        for bucket in manager.memory_manager.buckets.values():
            if channel.id == bucket.category.id or channel.category_id == bucket.category.id:
                return True

        return False

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        Log.info(f"Joined guild: {guild.name} ({guild.id})")
        
        if str(guild.id) in guilds_ids_db.get_all_keys():
            Log.warn("Guild is already saved in database, removing record...")
            guilds_ids_db.delete(guild.id)
        
        status = await setups.setup_guild_initialization(guild)
        if not status:
            Log.error(f"Failed to setup initailization process for guild {guild.name}")
            return
        
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        Log.warn(f"Removed from guild: {guild.name} ({guild.id})")
        
        if str(guild.id) in guilds_ids_db.get_all_keys():
            guilds_ids_db.delete(guild.id)
            
        for user in accounts.users_db.get_all_models():
            if guild.id in user.servers_ids:
                user.remove_instance(guild.id)
            
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error) -> None:
        if not console.is_console_channel(ctx):
            return
        
        if isinstance(error, commands.errors.CommandNotFound):
            return await ctx.reply(f"Error: `{error}`")
        
        raise error
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.TextChannel) -> None:
        if await self._is_crucial_channel(channel):
            await data.panic_guild_error(channel.guild, f"Removed crucial system/data channel: {channel.name}")
            
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if str(member.id) not in accounts.users_db.get_all_keys():
            welcome_embed = discord.Embed(
                color=assets.PRIMARY_COLOR,
                title=f"{assets.EMOJI_CLOUD} | Welcome to DriveCord.",
                description=f"You have joined DriveCord's instance: `{member.guild.name}` but You don't have DriveCord account yet."
                             f" Please use /register command to create new account. To interract with `{member.guild.name}` drive, ask administrator for permissions."
            )
            
            return await member.send(embed=welcome_embed)
            
        user = accounts.User.get_by_uid(member.id)
        user.assign_instance(member.guild.id)
        Log.info(f"{member.name} joined instance {member.guild.name}")
            
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.id == self.client.user.id:
            return
        
        manager = await data.DriveGuild.get(message.channel.guild)
        if message.channel.id != manager.console_channel.id:
            manager.memory_manager._removed_messages.append(message.id)
            await manager.log(f"{message.author.name} sent message at system channel: {message.channel.name} (removed)")
            await message.delete()
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        user = accounts.User.get_by_uid(member.id)
        if user is None:
            return Log.warn(f"Not registered user: {member.name} left instance: {member.guild.name}")
        
        user.remove_instance(member.guild.id)
    
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        if message.author.id != self.client.user.id:
            return
        
        manager = await data.DriveGuild.get(message.channel.guild)
        if message.channel.id == manager.console_channel.id:
            return
        if message.id in manager.memory_manager._removed_messages:
            return
        
        await data.panic_guild_error(message.guild, f"Removed client's message: {message.content}")
        
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role) -> None:
        manager = await data.DriveGuild.get(role.guild)
        if role.id in (manager.read_role.id, manager.write_role.id):
            await data.panic_guild_error(role.guild, f"Removed crucial role: {role.name}")
            
    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.TextChannel, after: discord.TextChannel) -> None:
        if not await self._is_crucial_channel(after) or before.name == after.name:
            return
        
        client_perms = after.permissions_for(self.client)
        if not all(client_perms.read_message_history, 
                   client_perms.read_messages, 
                   client_perms.send_messages, 
                   client_perms.manage_channels,
                   client_perms.manage_messages, 
                   client_perms.manage_roles
                   ):
            await data.panic_guild_error(after.guild, f"Missing crucial permissions after channel update: {after.name}")
        
   
async def setup(client: discord.Client) -> None:
    await client.add_cog(BotEvents(client))
    
    for guild in client.guilds:
        await data.DriveGuild.get(guild)
        
    Log.info("Initialized all guilds.")
        
