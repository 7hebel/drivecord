<div align="center">
    <br>
    <img src="./assets/banner.png" width="400" alt="Drivecord" />
    <h4>Custom filesystem stored on the Discord servers.</h4>
</div>

<div align="center">
    <br>
    <h2>📦 Install</h2>
</div>

1. Ensure [Python](https://www.python.org/downloads/) is installed and added to the PATH.

2. Clone the repository:
   
   ```bash
   git clone https://github.com/7hebel/drivecord.git
   ```
   
   or download as a ZIP and unpack.

3. Install the required dependencies:
   
   Open the terminal and navigate to the DriveCord's directory.
   
   ```bash
   pip install -r requirements.txt
   ```

4. Invite DriveCord bot to the Discord server:
   
    [🔗 Invite URL](https://discord.com/oauth2/authorize?client_id=1273050122451816599)

<div align="center">
    <br>
    <h2>👤 Account</h2>
</div>

In order to use DriveCord application, You must link Your Discord account with the DriveCord system. Respond to the Bot's private message or send it `/register` command.

<div align="center">
    <br>
    <h2>🗃️ Instances</h2>
</div>

Each DriveCord drive instance is a single Discord server with a initialized filesystem using the bot. 

**To create new instance** create new Discord server, [invite bot](https://discord.com/oauth2/authorize?client_id=1273050122451816599) and follow it's instructions.

You will be able to access data saved on the instance via the **Discord `#console` channel** or the **CLI client**.

<div align="center">
    <br>
    <h2>🎖️ Permissions</h2>
</div>

There are **4 roles** with different permissions that You can assign to the members.

- @Read - Can read filesystem and it's contents.

- @Write - Can alter filesystem and it's contents.

- @Admin - Can manage members (not @Owner).

- @Owner - Highest role, can manage admins.

Only @Owner which is the instance's author can assign @Admin role to other members.

<div align="center">
    <br>
    <h2>💬 Discord Console</h2>
</div>

The `#console` channel is the only channel in the server that You can write on. Writing on other channels may break the filesystem.

To get list of all available commands write the `help` command. To get more details about a command, use `help NAME`.

With the **Standard commands** You can alter the filesystem by creating, removing, renaming, moving, uploading or downloading, reading and writing the files and directories. 

The **Advanced commands** section contains commands that are used for debugging, avoid using these commands without deep understanding.

<div align="center">
    <br>
    <h2>💻 Command Line Interface</h2>
</div>

Download the CLI tool using the tutorial above. Navigate to the `/cli` directory in the terminal. Run client with `py main.py` and login with the DiscordID and password that You have registered DriveCord account with.

![CLI Login](https://raw.githubusercontent.com/7hebel/drivecord/refs/heads/main/assets/cli-login.png)

The command prompt contains dimmed selected instance name and the current working path (like in system terminals).

![CLI cwd](https://raw.githubusercontent.com/7hebel/drivecord/refs/heads/main/assets/cli-path.png)

Get list of all available commands with the `help` command. Here You can see all 4 categories (`System`, `Management`, `File system` and `Debug`). To get more detailed help with a single command, use `help CommandName`.

![CLI help](https://raw.githubusercontent.com/7hebel/drivecord/refs/heads/main/assets/cli-help.png)

The command line tool provides the same opportunities as the Discord Console.

<div align="center">
    <br>
    <h2>⚙️ Setup server</h2>
</div>

1. Download the server code from this repo.

2. Create Discord bot on the Discord Developer Portal.

3. Create `.env` file inside the `/server` directory.

```
DRIVECORD-TOKEN=...
DRIVECORD-HOST=...
DRIVECORD-PORT=...
```

4. Run server with the `py main.py` command.
