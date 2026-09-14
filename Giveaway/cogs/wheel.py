import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import checks, MissingAnyRole
import random
import asyncio
import aiosqlite

# 1. Manual Names System (/wheelnames)
class WheelNamesView(discord.ui.View):
    def __init__(self, host_id: int, names: list, giveaway_id: int, prize: str):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.names = names
        self.giveaway_id = giveaway_id
        self.prize = prize

    @discord.ui.button(label="Spin the Wheel 🎡", style=discord.ButtonStyle.primary, emoji="🎲")
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ Only the giveaway host can spin the wheel!", ephemeral=True)
            return

        button.disabled = True
        await interaction.response.edit_message(view=self)

        winner = random.choice(self.names)
        
        delays = [0.2, 0.4, 0.6, 0.8]
        for delay in delays:
            current_choice = random.choice(self.names)
            embed_spinning = discord.Embed(
                title="ZYNR",
                description=f"**Prize:** {self.prize}\n\n🎡 Spinning the wheel...\n🔄 Pointer is on: **{current_choice}**",
                color=discord.Color.gold()
            )
            embed_spinning.set_footer(text="Made by SharbelFr81")
            await interaction.message.edit(embed=embed_spinning)
            await asyncio.sleep(delay)

        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute("UPDATE giveaways SET winner = ?, status = 'closed' WHERE id = ?", (winner, self.giveaway_id))
            await db.commit()

        embed_result = discord.Embed(
            title="ZYNR - 🎉 Giveaway Result!",
            description=f"**Prize:** {self.prize}\n\n🏆 The winner is: **{winner}** 🏆\n\nCongratulations!",
            color=discord.Color.green()
        )
        embed_result.set_footer(text="Made by SharbelFr81")
        
        await interaction.message.edit(embed=embed_result, view=None)
        await interaction.channel.send(f"🎉 **{winner}** won **{self.prize}**! (Hosted by: <@{self.host_id}>)")


# 2. Interactive Join System (/wheel)
class InteractiveGiveawayView(discord.ui.View):
    def __init__(self, host_id: int, giveaway_id: int, prize: str):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.giveaway_id = giveaway_id
        self.prize = prize
        self.participants = [] 

    @discord.ui.button(label="Join Giveaway 🎉", style=discord.ButtonStyle.success, emoji="🎟️")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.mention in self.participants:
            await interaction.response.send_message("✅ You have already joined this giveaway!", ephemeral=True)
            return
        
        self.participants.append(interaction.user.mention)
        await interaction.response.send_message("🎉 You have successfully joined the giveaway!", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        embed.description = f"**Prize:** {self.prize}\n**Hosted by:** <@{self.host_id}>\n\n**Current Participants:** {len(self.participants)}"
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Draw Winner 🎡", style=discord.ButtonStyle.primary, emoji="🎲")
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ Only the giveaway host can spin the wheel!", ephemeral=True)
            return

        if len(self.participants) < 1:
            await interaction.response.send_message("❌ Not enough participants to draw a winner!", ephemeral=True)
            return

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        winner = random.choice(self.participants)
        
        delays = [0.2, 0.4, 0.6, 0.8]
        if len(self.participants) > 1:
            for delay in delays:
                current_choice = random.choice(self.participants)
                embed_spinning = discord.Embed(
                    title="ZYNR",
                    description=f"**Prize:** {self.prize}\n\n🎡 Spinning the wheel...\n🔄 Pointer is on: **{current_choice}**",
                    color=discord.Color.gold()
                )
                embed_spinning.set_footer(text="Made by SharbelFr81")
                await interaction.message.edit(embed=embed_spinning)
                await asyncio.sleep(delay)

        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute("UPDATE giveaways SET winner = ?, status = 'closed' WHERE id = ?", (winner, self.giveaway_id))
            await db.commit()

        embed_result = discord.Embed(
            title="ZYNR - 🎉 Giveaway Result!",
            description=f"**Prize:** {self.prize}\n\n🏆 The winner is: **{winner}** 🏆\n\nCongratulations!",
            color=discord.Color.green()
        )
        embed_result.set_footer(text="Made by SharbelFr81")
        
        await interaction.message.edit(embed=embed_result, view=None)
        await interaction.channel.send(f"🎉 **{winner}** won **{self.prize}**! (Hosted by: <@{self.host_id}>)")


class WheelCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute('''CREATE TABLE IF NOT EXISTS giveaways (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                host_id INTEGER,
                                prize TEXT,
                                status TEXT,
                                winner TEXT)''')
            await db.commit()

    @app_commands.command(name="wheelnames", description="Create a manual name raffle")
    @app_commands.describe(prize="The prize to win", participants="Names separated by commas (e.g. Alex, Mike, Sarah)")
    @checks.has_any_role("Leader", "Giveaway host")
    async def wheelnames_cmd(self, interaction: discord.Interaction, prize: str, participants: str):
        names = [name.strip() for name in participants.split(",") if name.strip()]

        if len(names) < 2:
            await interaction.response.send_message("❌ Please provide at least 2 names.", ephemeral=True)
            return

        async with aiosqlite.connect("giveaways.db") as db:
            cursor = await db.execute("INSERT INTO giveaways (host_id, prize, status) VALUES (?, ?, 'active')", 
                                      (interaction.user.id, prize))
            giveaway_id = cursor.lastrowid
            await db.commit()

        participants_list = "\n".join(f"• {name}" for name in names)
        embed = discord.Embed(
            title="ZYNR",
            description=f"**Prize:** {prize}\n**Hosted by:** {interaction.user.mention}\n\n**Participants:**\n{participants_list}",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Made by SharbelFr81")

        view = WheelNamesView(interaction.user.id, names, giveaway_id, prize)
        await interaction.response.send_message(embed=embed, view=view)

    @wheelnames_cmd.error
    async def wheelnames_error(self, interaction: discord.Interaction, error):
        if isinstance(error, MissingAnyRole):
            await interaction.response.send_message("❌ You do not have the required role to host a giveaway!", ephemeral=True)

    @app_commands.command(name="wheel", description="Create an interactive giveaway with a join button")
    @app_commands.describe(prize="The prize to win")
    @checks.has_any_role("Leader", "Giveaway host")
    async def wheel_cmd(self, interaction: discord.Interaction, prize: str):
        async with aiosqlite.connect("giveaways.db") as db:
            cursor = await db.execute("INSERT INTO giveaways (host_id, prize, status) VALUES (?, ?, 'active')", 
                                      (interaction.user.id, prize))
            giveaway_id = cursor.lastrowid
            await db.commit()

        embed = discord.Embed(
            title="ZYNR",
            description=f"**Prize:** {prize}\n**Hosted by:** {interaction.user.mention}\n\n**Current Participants:** 0",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made by SharbelFr81")

        view = InteractiveGiveawayView(interaction.user.id, giveaway_id, prize)
        await interaction.response.send_message(embed=embed, view=view)

    @wheel_cmd.error
    async def wheel_error(self, interaction: discord.Interaction, error):
        if isinstance(error, MissingAnyRole):
            await interaction.response.send_message("❌ You do not have the required role to host a giveaway!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WheelCog(bot))
