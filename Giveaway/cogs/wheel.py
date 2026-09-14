import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import aiosqlite

class WheelView(discord.ui.View):
    def __init__(self, host_id: int, names: list, giveaway_id: int):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.names = names
        self.giveaway_id = giveaway_id

    @discord.ui.button(label="Spin the Wheel", style=discord.ButtonStyle.primary, emoji="🎡")
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 4. Permissions Check: Only host can spin
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ Only the giveaway host can spin the wheel!", ephemeral=True)
            return

        button.disabled = True
        await interaction.response.edit_message(view=self)

        winner = random.choice(self.names)
        
        # 5. Dynamic Embeds: Spinning animation
        delays = [0.2, 0.4, 0.6, 0.8]
        for delay in delays:
            current_choice = random.choice(self.names)
            embed_spinning = discord.Embed(
                title="🎡 Spinning the Wheel...",
                description=f"🔄 Pointer is currently on: **{current_choice}**",
                color=discord.Color.gold()
            )
            await interaction.message.edit(embed=embed_spinning)
            await asyncio.sleep(delay)

        # 3. Database: Save the winner
        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute("UPDATE giveaways SET winner = ?, status = 'closed' WHERE id = ?", (winner, self.giveaway_id))
            await db.commit()

        # 5. Dynamic Embeds: Final result
        embed_result = discord.Embed(
            title="🎉 Giveaway Winner!",
            description=f"🏆 The winner is: **{winner}** 🏆\n\nCongratulations!",
            color=discord.Color.green()
        )
        embed_result.set_footer(text=f"Giveaway ID: #{self.giveaway_id}")
        
        await interaction.message.edit(embed=embed_result, view=None)
        
        # Ping in channel
        await interaction.channel.send(f"🎉 **{winner}** won the giveaway hosted by {interaction.user.mention}!")


class WheelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Initialize SQLite database table
    async def cog_load(self):
        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS giveaways (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                host_id INTEGER,
                                names TEXT,
                                winner TEXT,
                                status TEXT)''')
            await db.commit()

    # 1. Slash Command (/)
    @app_commands.command(name="wheel", description="Create a spinning wheel raffle")
    @app_commands.describe(participants="Names separated by commas (e.g. Alex, Mike, Sarah)")
    async def wheel_cmd(self, interaction: discord.Interaction, participants: str):
        names = [name.strip() for name in participants.split(",") if name.strip()]

        if len(names) < 2:
            await interaction.response.send_message("❌ Please provide at least 2 names.", ephemeral=True)
            return

        # Insert new giveaway into Database
        async with aiosqlite.connect("giveaways.db") as db:
            cursor = await db.execute("INSERT INTO giveaways (host_id, names, status) VALUES (?, ?, 'active')", 
                                      (interaction.user.id, participants))
            giveaway_id = cursor.lastrowid
            await db.commit()

        participants_list = "\n".join(f"• {name}" for name in names)
        embed = discord.Embed(
            title="🎡 Name Raffle Wheel",
            description=f"Hosted by: {interaction.user.mention}\n\n**Participants:**\n{participants_list}",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Only the host can spin this wheel!")

        view = WheelView(interaction.user.id, names, giveaway_id)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(WheelCog(bot))