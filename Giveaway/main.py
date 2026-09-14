import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        # 6. Advanced Code Structure: Load the Wheel cog
        await self.load_extension("cogs.wheel")
        # Sync Slash Commands to Discord
        await self.tree.sync()
        print("✅ Slash commands synced!")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user.name} ({bot.user.id})")
    print("🤖 Professional Bot is ready!")

# Start Web Server
keep_alive()

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)