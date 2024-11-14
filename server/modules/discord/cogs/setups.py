from modules.discord.data import DriveGuild
from modules.discord.client import client
from modules.discord import pointers
from modules.discord.assets import *
from modules.filesystem import fs
from modules import accounts
from modules import errors

from modules.logs import Log
import discord
import bcrypt
import base64


class AccountRegistrationModal(discord.ui.Modal, title="☁️ Create DriveCord account."):
    account_password = discord.ui.TextInput(
        label="🔐 Create password.",
        placeholder="...",
        required=True,
        min_length=3,
    )

    account_repeat_password = discord.ui.TextInput(
        label="🔁 Repeat password.",
        placeholder="...",
        required=True,
        min_length=3,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        password = self.account_password.value
        password_repeat = self.account_repeat_password.value
        user_id = interaction.user.id

        if password != password_repeat:
            embed_error = discord.Embed(
                title="Passwords not matching...",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed_error)
            return

        if str(user_id) in accounts.users_db.get_all_keys():
            embed_error = discord.Embed(
                title="This account is already registered.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed_error)
            return

        password_enc = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        accounts.User.register(user_id, password_enc)

        embed_success = discord.Embed(
            title="Account registered ✅",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed_success)
        return


class RegisterUserButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Register', style=discord.ButtonStyle.green, custom_id='register:account', emoji=EMOJI_ACCOUNT)
    async def connect_accounts(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AccountRegistrationModal())


async def register_user(user: discord.User, guild: discord.Guild) -> accounts.User | errors.T_Error:
    start_registration_embed = discord.Embed(
        color=PRIMARY_COLOR,
        description=f"# {EMOJI_ACCOUNT} | Register account.\nStart using **DriveCord** with Your **Discord** account.",
    )

    try:
        await user.send(embed=start_registration_embed, view=RegisterUserButton())

    except discord.Forbidden:
        Log.warn(f"Failed to send registration message to user: {user.id}")
        await guild.system_channel.send(embed=start_registration_embed, content=f"{user.mention}")


class InitializationSetupDecision(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='Continue', style=discord.ButtonStyle.blurple, emoji=EMOJI_CLOUD)
    async def continue_initialization(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.guild.owner_id) not in accounts.users_db.get_all_keys():
            no_account_embed = discord.Embed(
                color=discord.Color.red(),
                title="Create account to continue (check DM)"
            )
            await interaction.response.send_message(embed=no_account_embed, ephemeral=True)
            return

        if interaction.user.id != interaction.guild.owner_id:
            not_owner_embed = discord.Embed(
                color=discord.Color.red(),
                title="You are not guild's owner."
            )
            await interaction.response.send_message(embed=not_owner_embed, ephemeral=True)
            return

        await initialize_guild(interaction.guild)

    @discord.ui.button(label='Abort', style=discord.ButtonStyle.red)
    async def abort_initialization(self, interaction: discord.Interaction, button: discord.ui.Button):
        Log.error(f"Initialization setup manually aborted for guild {interaction.guild.name}. Leaving guild...")
        abort_embed = discord.Embed(
            color=discord.Color.red(),
            title=f"{EMOJI_CLOUD} | Initializaiton aborted, exiting..."
        )

        await interaction.response.send_message(embed=abort_embed)
        await interaction.guild.leave()


async def setup_guild_initialization(guild: discord.Guild) -> bool:
    """ Setup filesystem in given guild. Returns status. """
    owner = guild.owner
    owner_id = str(owner.id)

    # Check owner's account.
    if owner_id not in accounts.users_db.get_all_keys():
        account = await register_user(owner, guild)
        if isinstance(account, errors.T_Error):
            Log.error("Initialization fail: registration failed.")
            return False
    else:
        account = accounts.users_db.get(owner_id)

    # Check bot's permissions.
    bot = guild.get_member(client.user.id)
    if not bot.top_role.permissions.administrator:
        perm_error = discord.Embed(title="DriveCord bot has no `administrator` permission!", color=discord.Color.red())
        Log.error(f"Leaving guild: {guild.name} (permission error)")
        await owner.send(embed=perm_error)
        await guild.leave()
        return False

    # Choose setup channel.
    setup_channel: discord.TextChannel | None = guild.system_channel
    if setup_channel is None:
        if guild.text_channels:
            Log.warn(f"No system channel found on guild {guild.name}, using first text channel.")
            setup_channel = guild.text_channels[0]

        else:
            Log.warn(f"No text channel found on guild {guild.name}, creating...")
            setup_channel = await guild.create_text_channel("setup")

    # Send initialization message.
    setup_warn_msg = discord.Embed(
        color=0xb7aae0,
        description=f"# {EMOJI_WARN} | Initialize DriveCord.\n### WARNING:\n```This will erease all channels and categories and make this server unusable!```\n\nDo You want to continue?"
    )

    await setup_channel.send(embed=setup_warn_msg, view=InitializationSetupDecision())
    return True


async def initialize_guild(guild: discord.Guild) -> None:
    """ Remove all categories, channels and kick all members except owner. Create default structure. """
    # Remove data from DB if reinit.
    try:
        pointers.guilds_ids_db.delete(guild.id)
    except pointers.database.KeyNotFound:
        pass
    
    # Clear current objects.
    ch_count = 0

    for channel in guild.channels:
        ch_count += 1
        await channel.delete(reason="DriveCord initialization process")

    Log.info(f"{guild.name} initialization: removed {ch_count} channels")

    # Create access roles.
    owner_role = await guild.create_role(name="DriveCord-owner", permissions=discord.Permissions.all(), color=PRIMARY_COLOR, hoist=True)
    await guild.owner.add_roles(owner_role)
    admin_role = await guild.create_role(name="DriveCord-admin", permissions=discord.Permissions(66560), color=0x63568c, hoist=True)
    write_role = await guild.create_role(name="DriveCord-write", permissions=discord.Permissions(66560), color=0xeb7a34, hoist=True)
    read_role = await guild.create_role(name="DriveCord-read", permissions=discord.Permissions(66560), color=0x34a8eb, hoist=True)

    # Create channels.
    system_category_perms = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)
    }
    
    console_channel = await guild.create_text_channel("console")
    meta_category = await guild.create_category("meta", overwrites=system_category_perms)
    logs_channel = await guild.create_text_channel("_logs", category=meta_category)
    struct_channel = await guild.create_text_channel("_struct", category=meta_category)
    data0_category = await guild.create_category("data_0", overwrites=system_category_perms)
    await guild.create_text_channel("_cache", category=data0_category)
    await guild.create_text_channel("0", category=data0_category)
    await guild.edit(system_channel=console_channel)

    base_struct = fs.FS_Dir("~", None)
    struct_export = base_struct.export()
    struct_content = base64.b64encode(struct_export.encode()).decode()
    await struct_channel.send(struct_content)

    db_data = pointers._GuildPointers(
        guild_id=guild.id,
        console_id=console_channel.id,
        logs_id=logs_channel.id,
        struct_id=struct_channel.id,
        read_role=read_role.id,
        write_role=write_role.id,
        admin_role=admin_role.id
    )
    pointers.guilds_ids_db.insert(db_data)

    await DriveGuild.init(guild)

    for member_id in guild._members.keys():
        user = accounts.User.get_by_uid(member_id)
        if user is None:
            continue
        
        user.assign_instance(guild.id)

    Log.info(f"{guild.name} initialization: Created roles and channels.")
    Log.info(f"{guild.name} Finished initialization process.")

    info_message = discord.Embed(
        color=PRIMARY_COLOR,
        description=f"# {EMOJI_CLOUD} | DriveCord initialization finished.\n"
                    f"### {EMOJI_WARN} DO NOT:\n"
                    "- Create/delete/update/manage any channels, categories and roles.\n"
                    "- Send messages on any channels except this one.\n"
                    "- Manage bot's and members permissions.\n"
                    "- Interrupt DriveCord's work.\n"
                    "```Performing forbidden actions may **irreversibly break** this DriveCord instance including Your data.```\n"
                    f"### {EMOJI_ACCOUNT} OTHER USERS:\n"
                    "To interract with data saved on this drive, members must have created and linked DriveCord account. "
                    "Manage their permissions using bot's commands. Don't do it manually!\n\n"
                    f"### {EMOJI_CLOUD} MANAGE DRIVE:\n"
                    f"You can access data saved on this drive and manage it using DriveCord website, CLI tool or {console_channel.mention} channel. (Use `help` command to get commands list.)"
    )

    await console_channel.send(embed=info_message)
