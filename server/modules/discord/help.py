from modules.discord import assets

from discord.ext import commands
import discord


class CustomHelpCommand(commands.HelpCommand):

    async def send_bot_help(self, mapping: dict):
        embed = discord.Embed(title=f"{assets.EMOJI_CLI} DriveCord console help.", color=assets.PRIMARY_COLOR)
        all_cmds: list[commands.Command] = [c for cmds in mapping.values() for c in cmds]
        std_cmds: list[commands.Command] = []
        adv_cmds: list[commands.Command] = []
        
        for cmd in all_cmds:
            if cmd.name.startswith("_"):
                adv_cmds.append(cmd)
            else:
                std_cmds.append(cmd)
        
        # .name - Name
        # .brief - Attrs syntax
        # .help - Help text
        # .aliases - List of aliases
        # .usage - Required perms.
        embed.description = "# Standard commands:"
        for cmd in std_cmds:
            cmd_content = f"### `{cmd.name}`\n"
            if cmd.aliases:
                cmd_content += f"* *[{', '.join(cmd.aliases)}]*\n"
            if cmd.usage:
                cmd_content += f"* Permission: `{cmd.usage}`\n"
            cmd_content += f"* {cmd.help}\n"
            if cmd.brief:
                cmd_content += f"* `{cmd.brief}`"
            
            embed.description += f"\n{cmd_content}"
            
        embed.description += "\n# Advanced commands:\n**All advanced commands require `Admin` permissions!**"
        for cmd in adv_cmds:
            cmd_content = f"### `{cmd.name}`\n"
            if cmd.aliases:
                cmd_content += f"* *[{', '.join(cmd.aliases)}]*\n"
            cmd_content += f"* {cmd.help}\n"
            if cmd.brief:
                cmd_content += f"* `{cmd.brief}`"
            
            embed.description += f"\n{cmd_content}"
            
        channel = self.get_destination()
        await channel.send(embed=embed)
        
    async def send_command_help(self, command: commands.Command) -> None:
        embed = discord.Embed(title=f"{assets.EMOJI_CLI} DriveCord command.", color=assets.PRIMARY_COLOR)
        aliases = ", ".join([f"`{a}`" for a in command.aliases]) if command.aliases else "*No aliases.*"
        syntax = f"`{command.brief}`" if command.brief else "*No attributes.*"
        perms = f"`{command.usage}`" if command.usage else "*No permission required.*"
        embed.description = f"# `{command.name}`\n{command.help}\n\n* **Aliases:** {aliases}\n* **Permission:** {perms}\n* **Syntax:** {syntax}"
        
        channel = self.get_destination()
        await channel.send(embed=embed)
        