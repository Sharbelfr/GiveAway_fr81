import discord
from discord.ext import commands
from discord.ui import View, Button
import random
import asyncio
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup bot intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

class GiveawayView(View):
    def __init__(self, names):
        super().__init__(timeout=None)
        self.names = names

    @discord.ui.button(label="Spin the Wheel", style=discord.ButtonStyle.primary, emoji="🎡")
    async def spin(self, interaction: discord.Interaction, button: Button):
        # Disable button during spin to prevent duplicate clicks
        button.disabled = True
        await interaction.response.edit_message(view=self)

        winner = random.choice(self.names)

        # Simulate wheel spinning animation with gradual slowing
        delays = [0.15, 0.2, 0.3, 0.45, 0.6]
        for delay in delays:
            current_choice = random.choice(self.names)
            embed_spinning = discord.Embed(
                title="🎡 Spinning the Wheel...",
                description=f"🔄 Pointer on: **{current_choice}**",
                color=discord.Color.gold()
            )
            await interaction.message.edit(embed=embed_spinning)
            await asyncio.sleep(delay)

        # Announce final winner
        embed_result = discord.Embed(
            title="🎉 Giveaway Winner!",
            description=f"🏆 The winner is: **{winner}** 🏆\n\nCongratulations!",
            color=discord.Color.green()
        )
        button.disabled = False
        await interaction.message.edit(embed=embed_result, view=self)

@bot.command()
async def wheel(ctx, *, args: str):
    """
    Usage:
    !wheel John, Mike, Alex, David
    """
    names = [name.strip() for name in args.split(",") if name.strip()]

    if len(names) < 2:
        await ctx.send("Please provide at least 2 names separated by commas (`,`).")
        return

    participants_list = "\n".join(f"• {name}" for name in names)
    embed = discord.Embed(
        title="🎡 Name Raffle Wheel",
        description=f"Click the button below to spin the wheel and pick a random winner!\n\n**Participants:**\n{participants_list}",
        color=discord.Color.blurple()
    )

    view = GiveawayView(names)
    await ctx.send(embed=embed, view=view)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print("Bot is ready!")

# Retrieve token from environment variables
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is not set. Please add it to your .env file.")

bot.run(TOKEN)