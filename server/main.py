from modules.discord.client import client
from modules import logs
from modules import api

from dotenv import load_dotenv
import threading
import uvicorn
import os


env_status = load_dotenv()
if not env_status:
    raise EnvironmentError("No .env file found.")


def main():
    api_host = os.getenv("DRIVECORD-HOST") or "localhost"
    api_port = int(os.getenv("DRIVECORD-PORT")) or 8000
    discord_token = os.getenv("DRIVECORD-TOKEN")
    if discord_token is None:
        raise EnvironmentError("`DRIVECORD-TOKEN` value not found in .env")
    
    discord_thread = threading.Thread(target=client.run, args=(discord_token, ), kwargs={"log_formatter": logs._DCLogFormatter()}, daemon=True)
    discord_thread.start()
    uvicorn.run(api.api, host=api_host, port=api_port, access_log=True)


if __name__ == "__main__":
    main()
