from modules.discord.cogs import setups
from modules.discord.assets import *
from modules.discord import data
from modules import timestamp
from modules import accounts
from modules import limits
from modules import perms

from discord.ext import commands
from discord import app_commands
import discord


def _build_perms_toogle_buttons(caller_perms: perms.DrivePermissions, user: discord.Member, perms: perms.DrivePermissions) -> discord.ui.View:
    read_style = discord.ButtonStyle.green if perms.read else discord.ButtonStyle.red
    read_text = "Read: YES" if perms.read else "Read: NO"
    read_emoji = "✅" if perms.read else "✖️"
    read_locked = perms.admin
    
    write_style = discord.ButtonStyle.green if perms.write else discord.ButtonStyle.red
    write_text = "Write: YES" if perms.write else "Write: NO"
    write_emoji = "✅" if perms.write else "✖️"
    write_locked = perms.admin

    admin_style = discord.ButtonStyle.green if perms.admin else discord.ButtonStyle.red
    admin_text = "Admin: YES" if perms.admin else "Admin: NO"
    admin_emoji = "✅" if perms.admin else "✖️"
    admin_locked = not caller_perms.owner

    class _PermsManagementButtons(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label=read_text, style=read_style, emoji=read_emoji, disabled=read_locked)
        async def toogle_read(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not read_locked:
                perms.update(read=not perms.read)
                
            drive_man = await data.DriveGuild.get(interaction.guild)
            await drive_man.set_permissions(user, perms)
            await interaction.response.edit_message(view=_build_perms_toogle_buttons(caller_perms, user, perms))

        @discord.ui.button(label=write_text, style=write_style, emoji=write_emoji, disabled=write_locked)
        async def toogle_write(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not write_locked:
                perms.update(write=not perms.write)
                
            drive_man = await data.DriveGuild.get(interaction.guild)
            await drive_man.set_permissions(user, perms)
            await interaction.response.edit_message(view=_build_perms_toogle_buttons(caller_perms, user, perms))

        @discord.ui.button(label=admin_text, style=admin_style, emoji=admin_emoji, disabled=admin_locked)
        async def toogle_admin(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not admin_locked:
                perms.update(admin=not perms.admin)
                
            drive_man = await data.DriveGuild.get(interaction.guild)
            await drive_man.set_permissions(user, perms)
            await interaction.response.edit_message(view=_build_perms_toogle_buttons(caller_perms, user, perms))
            
    return _PermsManagementButtons()


class BotTreeCommands(commands.Cog):
    def __init__(self, client: discord.Client) -> None:
        self.client = client

    @app_commands.command(name="ping", description="🏓 Check if bot is responding.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=discord.Embed(title="Pong 🏓", color=PRIMARY_COLOR), ephemeral=True)

    @app_commands.command(name="register", description="👤 Register DriveCord account.")
    async def manual_register(self, interaction: discord.Interaction):
        if str(interaction.user.id) in accounts.users_db.get_all_keys():
            embed_error = discord.Embed(
                title="This account is already registered.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed_error)
            
        start_registration_embed = discord.Embed(
            color=PRIMARY_COLOR,
            description=f"# {EMOJI_ACCOUNT} | Register account.\nStart using **DriveCord** with Your **Discord** account.",
        )
        
        await interaction.response.send_message(embed=start_registration_embed, view=setups.RegisterUserButton(), ephemeral=True)

    @app_commands.command(name="permissions", description="🔒 Manage users permissions.")
    async def manage_perms(self, interaction: discord.Interaction, member: discord.User):
        if interaction.guild is None:
            embed_error = discord.Embed(
                title="This command can be used only within DriveCord server instance.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed_error)

        if str(interaction.user.id) not in accounts.users_db.get_all_keys():
            embed_error = discord.Embed(
                title="You are not registered DriveCord user. (Use /register)",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed_error)
          
        drive_man = await data.DriveGuild.get(interaction.guild)
        caller_perms = drive_man.get_permissions(interaction.user)
        member_perms = drive_man.get_permissions(member)
        
        if not caller_perms.admin:
            return await interaction.response.send_message(embed=perms.ADMIN_PERMS_ERROR_EMBED, ephemeral=True)

        if str(member.id) not in accounts.users_db.get_all_keys():
            embed_error = discord.Embed(
                title=f"Selected user: `{member.name}` has no DriveCord account yet. They cannot interract with the drive.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed_error, ephemeral=True)

        if member_perms.owner:
            embed_error = discord.Embed(
                title=f"Selected user: `{member.name}` has `OWNER` permission. Their permissions cannot be managed.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed_error, ephemeral=True)
            
        if member_perms.admin and not caller_perms.owner:
            embed_error = discord.Embed(
                title=f"Selected user: `{member.name}` has `ADMIN` permission. To manage their permissions `OWNER` permission is required.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed_error, ephemeral=True)

        toogle_buttons = _build_perms_toogle_buttons(caller_perms, member, member_perms)
        embed_info = discord.Embed(
            title=f"{EMOJI_ACCOUNT} | Manage `{member.name}` permissions.",
            description="Use buttons below to toogle user's permissions.",
            color=PRIMARY_COLOR
        )
        
        return await interaction.response.send_message(embed=embed_info, ephemeral=True, view=toogle_buttons)

    @app_commands.command(name="access-tokens", description="🎫 Manage active CLI access tokens.")
    async def list_access_tokens(self, interaction: discord.Interaction):
        if str(interaction.user.id) not in accounts.users_db.get_all_keys():
            embed_error = discord.Embed(
                title="You are not registered DriveCord user. (Use /register)",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed_error, ephemeral=True)
        
        account = accounts.User.get_by_uid(interaction.user.id)

        if not account.access_tokens:
            embed_error = discord.Embed(
                title="You have no active access tokens.",
                description="Login with CLI tool to automatically generate new token.",
                color=PRIMARY_COLOR
            )
            return await interaction.response.send_message(embed=embed_error, ephemeral=True)

        select_options = []
        tokens_embed = discord.Embed(
            title=f"🎫 Active access tokens ({len(account.access_tokens)}/{limits.MAX_ACCESS_TOKENS})",
            color=PRIMARY_COLOR
        )
        
        for token in account.access_tokens:
            tokens_embed.add_field(
                name=f"`{token.masked}...`",
                value=f"- **Generated:** `{timestamp.convert_to_readable(token.date_created)}`\n- **IP (hashed):** `{token.ip_address[:5]}...`"
            )

            select_options.append(
                discord.SelectOption(label=token.masked, emoji="❌", description="Revoke access for this token.", value=token.token_id)
            )

        async def revoke_callback(interaction: discord.Interaction) -> None:
            revoke_token_id = selection.values[0]
            account.burn_access_token(revoke_token_id)

            embed_success = discord.Embed(
                title=f"Burned token `{revoke_token_id[:5]}...`",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed_success, ephemeral=True)
            
        selection = discord.ui.Select(
            options=select_options,
            placeholder="Select access token to revoke."
        )
        selection.callback = revoke_callback
        
        view = discord.ui.View()
        view.add_item(selection)

        await interaction.response.send_message(embed=tokens_embed, view=view, ephemeral=True)


async def setup(client: discord.Client) -> None:
    await client.add_cog(BotTreeCommands(client))
    