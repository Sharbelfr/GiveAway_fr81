import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import checks, MissingAnyRole
import random
import asyncio
import aiosqlite
import datetime

# 🔴 Basic Bot Settings 🔴
ALLOWED_CHANNEL_IDS = [1549031641660526753, 1548116799529422970] 
ALLOWED_ROLES = ["Giveaway host", "Admin", 123456789012345678] 

def in_allowed_channels():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.channel_id in ALLOWED_CHANNEL_IDS
    return app_commands.check(predicate)

# ==========================================
# 0. Post-Giveaway View (Reroll Button)
# ==========================================
class EndedGiveawayView(discord.ui.View):
    def __init__(self, host_id: int, giveaway_id: int, prize: str, participants: list):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.giveaway_id = giveaway_id
        self.prize = prize
        self.participants = participants

    @discord.ui.button(label="Reroll 🎲", style=discord.ButtonStyle.secondary, custom_id="reroll_btn")
    async def reroll_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ Only the giveaway host can reroll!", ephemeral=True)
            return

        if len(self.participants) < 1:
            await interaction.response.send_message("❌ Not enough participants to reroll!", ephemeral=True)
            return

        new_winner = random.choice(self.participants)
        
        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute("UPDATE giveaways SET winner = ? WHERE id = ?", (new_winner, self.giveaway_id))
            await db.commit()

        await interaction.response.send_message(f"🎲 **Reroll!**\nThe new winner for **{self.prize}** is: {new_winner} 🎉")

# ==========================================
# 1. Manual Names Giveaway
# ==========================================
class WheelNamesView(discord.ui.View):
    def __init__(self, host_id: int, names: list, giveaway_id: int, prize: str):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.names = names
        self.giveaway_id = giveaway_id
        self.prize = prize

    @discord.ui.button(label="Spin Wheel 🎡", style=discord.ButtonStyle.primary, emoji="🎲")
    async def spin(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ Only the giveaway host can spin the wheel!", ephemeral=True)
            return

        button.disabled = True
        await interaction.response.edit_message(view=self)
        winner = random.choice(self.names)
        
        embed_spinning = discord.Embed(
            title="🎁 ZYNR Giveaway 🎁",
            description=f"**Prize:** {self.prize}\n\n🎡 Spinning the wheel...",
            color=discord.Color.gold()
        )
        embed_spinning.set_image(url="https://i.makeagif.com/media/7-29-2015/aO09R5.gif")
        embed_spinning.set_footer(text="Made by SharbelFr81")
        await interaction.message.edit(embed=embed_spinning)
        
        await asyncio.sleep(3)

        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute("UPDATE giveaways SET winner = ?, status = 'closed' WHERE id = ?", (winner, self.giveaway_id))
            await db.commit()

        embed_result = discord.Embed(title="🎉 ZYNR - Giveaway Result! 🎉", color=discord.Color.green())
        embed_result.add_field(name="Prize", value=f"**{self.prize}**", inline=False)
        embed_result.add_field(name="🏆 Winner", value=f"**{winner}**", inline=False)
        embed_result.add_field(name="Hosted By", value=f"<@{self.host_id}>", inline=True)
        embed_result.set_footer(text="Made by SharbelFr81")
        
        ended_view = EndedGiveawayView(self.host_id, self.giveaway_id, self.prize, self.names)
        await interaction.message.edit(embed=embed_result, view=ended_view)
        await interaction.channel.send(f"🎉 **{winner}** won **{self.prize}**! (Hosted by: <@{self.host_id}>)")

class WheelNamesModal(discord.ui.Modal, title='Manual Giveaway Details'):
    prize = discord.ui.TextInput(label='Prize', placeholder='What is the prize?', required=True)
    names = discord.ui.TextInput(label='Participants', style=discord.TextStyle.paragraph, placeholder='Names separated by commas', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        names_list = [name.strip() for name in self.names.value.split(",") if name.strip()]
        if len(names_list) < 2:
            await interaction.response.send_message("❌ Please provide at least 2 names.", ephemeral=True)
            return

        participants_str = ",".join(names_list)
        async with aiosqlite.connect("giveaways.db") as db:
            cursor = await db.execute("INSERT INTO giveaways (host_id, prize, status, participants) VALUES (?, ?, 'active', ?)", 
                                      (interaction.user.id, self.prize.value, participants_str))
            giveaway_id = cursor.lastrowid
            await db.commit()

        embed = discord.Embed(title="🎁 ZYNR Giveaway (Manual) 🎁", color=discord.Color.blurple())
        embed.add_field(name="🏆 Prize", value=f"**{self.prize.value}**", inline=False)
        embed.add_field(name="👑 Hosted By", value=f"{interaction.user.mention}", inline=True)
        embed.add_field(name="👥 Participants", value="\n".join(f"• {n}" for n in names_list), inline=False)
        embed.set_footer(text="Made by SharbelFr81")
        
        view = WheelNamesView(interaction.user.id, names_list, giveaway_id, self.prize.value)
        await interaction.response.send_message(embed=embed, view=view)


# ==========================================
# 2. Interactive Giveaway & Control Panel
# ==========================================
class InteractiveGiveawayView(discord.ui.View):
    def __init__(self, host_id: int, giveaway_id: int, prize: str, end_timestamp: int):
        super().__init__(timeout=None)
        self.host_id = host_id
        self.giveaway_id = giveaway_id
        self.prize = prize
        self.end_timestamp = end_timestamp
        self.participants = [] 
        self.message = None
        self.ended = False

    @discord.ui.button(label="Join Giveaway 🎉", style=discord.ButtonStyle.success, emoji="🎟️", custom_id="join_btn")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.mention in self.participants:
            await interaction.response.send_message("✅ You have already joined!", ephemeral=True)
            return
        
        self.participants.append(interaction.user.mention)
        await interaction.response.send_message("🎉 You joined the giveaway successfully!", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        embed.set_field_at(3, name="👥 Participants", value=f"**{len(self.participants)}**", inline=True)
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="End Now 🛑", style=discord.ButtonStyle.danger, custom_id="end_btn")
    async def end_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ Only the host can use control panel buttons!", ephemeral=True)
            return
        await interaction.response.defer()
        await self.auto_end_giveaway(manual=True)

    @discord.ui.button(label="Cancel ❌", style=discord.ButtonStyle.secondary, custom_id="cancel_btn")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("❌ Only the host can use control panel buttons!", ephemeral=True)
            return
        
        self.ended = True
        for child in self.children:
            child.disabled = True
        
        embed_cancel = discord.Embed(
            title="ZYNR - ❌ Giveaway Cancelled",
            description=f"The giveaway for **{self.prize}** was cancelled by the host.",
            color=discord.Color.red()
        )
        embed_cancel.set_footer(text="Made by SharbelFr81")
        
        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute("UPDATE giveaways SET status = 'cancelled' WHERE id = ?", (self.giveaway_id,))
            await db.commit()

        await interaction.message.edit(embed=embed_cancel, view=self)

    async def auto_end_giveaway(self, manual=False):
        if self.ended or not self.message: return
        self.ended = True

        for child in self.children:
            child.disabled = True

        if len(self.participants) == 0:
            embed_cancel = discord.Embed(title="ZYNR - ❌ Giveaway Failed", description="Giveaway ended with no participants.", color=discord.Color.red())
            embed_cancel.set_footer(text="Made by SharbelFr81")
            await self.message.edit(embed=embed_cancel, view=self)
            return

        winner = random.choice(self.participants)
        
        embed_spinning = discord.Embed(
            title="🎁 ZYNR Giveaway 🎁",
            description=f"**Prize:** {self.prize}\n\n🎡 Spinning the wheel...",
            color=discord.Color.gold()
        )
        embed_spinning.set_image(url="https://i.makeagif.com/media/7-29-2015/aO09R5.gif")
        embed_spinning.set_footer(text="Made by SharbelFr81")
        await self.message.edit(embed=embed_spinning, view=self)
        
        await asyncio.sleep(3)
        
        embed_result = discord.Embed(title="🎉 ZYNR - Giveaway Result! 🎉", color=discord.Color.green())
        embed_result.add_field(name="Prize", value=f"**{self.prize}**", inline=False)
        embed_result.add_field(name="🏆 Winner", value=f"**{winner}**", inline=False)
        embed_result.add_field(name="Hosted By", value=f"<@{self.host_id}>", inline=True)
        embed_result.add_field(name="Total Participants", value=f"**{len(self.participants)}**", inline=True)
        embed_result.set_footer(text=f"Giveaway ID: {self.giveaway_id} • Made by SharbelFr81")
        
        participants_str = ",".join(self.participants)
        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute("UPDATE giveaways SET winner = ?, status = 'closed', participants = ? WHERE id = ?", (winner, participants_str, self.giveaway_id))
            await db.commit()

        ended_view = EndedGiveawayView(self.host_id, self.giveaway_id, self.prize, self.participants)
        await self.message.edit(embed=embed_result, view=ended_view)
        await self.message.channel.send(f"🎉 Congratulations **{winner}**! You won **{self.prize}**! (Hosted by: <@{self.host_id}>)")

class InteractiveGiveawayModal(discord.ui.Modal, title='Timed Giveaway Details'):
    prize = discord.ui.TextInput(label='Prize', placeholder='What is the prize?', required=True)
    duration = discord.ui.TextInput(label='Duration (minutes)', placeholder='e.g., 10', required=True, max_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.duration.value)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number for duration.", ephemeral=True)
            return

        end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        unix_timestamp = int(end_time.timestamp())

        async with aiosqlite.connect("giveaways.db") as db:
            cursor = await db.execute("INSERT INTO giveaways (host_id, prize, status) VALUES (?, ?, 'active')", 
                                      (interaction.user.id, self.prize.value))
            giveaway_id = cursor.lastrowid
            await db.commit()

        embed = discord.Embed(
            title="🎁 ZYNR Giveaway 🎁",
            description="Click the button below to enter!",
            color=discord.Color.blue()
        )
        embed.add_field(name="🏆 Prize", value=f"**{self.prize.value}**", inline=False)
        embed.add_field(name="👑 Hosted By", value=f"{interaction.user.mention}", inline=True)
        embed.add_field(name="⏳ Ends In", value=f"<t:{unix_timestamp}:R>", inline=True)
        embed.add_field(name="👥 Participants", value="**0**", inline=True)
        embed.set_footer(text=f"Giveaway ID: {giveaway_id} • Made by SharbelFr81")

        view = InteractiveGiveawayView(interaction.user.id, giveaway_id, self.prize.value, unix_timestamp)
        await interaction.response.send_message(embed=embed, view=view)
        
        view.message = await interaction.original_response()
        
        asyncio.create_task(self.wait_and_end(view, minutes))

    async def wait_and_end(self, view, minutes):
        await asyncio.sleep(minutes * 60)
        if not view.ended:
            await view.auto_end_giveaway()


# ==========================================
# 3. Main Cog & Commands
# ==========================================
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
                                winner TEXT,
                                participants TEXT)''')
            await db.commit()

    @app_commands.command(name="wheelnames", description="Create a manual name raffle with a UI Modal")
    @checks.has_any_role(*ALLOWED_ROLES)
    @in_allowed_channels()
    async def wheelnames_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_modal(WheelNamesModal())

    @app_commands.command(name="wheel", description="Create a timed interactive giveaway with a Host Panel")
    @checks.has_any_role(*ALLOWED_ROLES)
    @in_allowed_channels()
    async def wheel_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_modal(InteractiveGiveawayModal())

    @app_commands.command(name="reroll", description="Draw a new winner for a previous giveaway")
    @app_commands.describe(giveaway_id="Giveaway ID")
    @checks.has_any_role(*ALLOWED_ROLES)
    @in_allowed_channels()
    async def reroll_cmd(self, interaction: discord.Interaction, giveaway_id: int):
        async with aiosqlite.connect("giveaways.db") as db:
            async with db.execute("SELECT prize, status, participants FROM giveaways WHERE id = ?", (giveaway_id,)) as cursor:
                row = await cursor.fetchone()

        if not row:
            return await interaction.response.send_message("❌ Giveaway ID not found.", ephemeral=True)
            
        prize, status, participants_str = row
        if status != 'closed' or not participants_str:
            return await interaction.response.send_message("❌ This giveaway is not completed, or has no participants to reroll.", ephemeral=True)

        participants = participants_str.split(",")
        new_winner = random.choice(participants)

        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute("UPDATE giveaways SET winner = ? WHERE id = ?", (new_winner, giveaway_id))
            await db.commit()

        embed = discord.Embed(title="🎲 ZYNR - Reroll Result", description=f"A new winner was drawn for: **{prize}**\n\n🏆 The new winner is: **{new_winner}**", color=discord.Color.gold())
        embed.set_footer(text="Made by SharbelFr81")
        await interaction.response.send_message(embed=embed)

    async def handle_error(self, interaction, error):
        if isinstance(error, MissingAnyRole):
            await interaction.response.send_message("❌ You do not have the required role to host a giveaway!", ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure):
            allowed_channels_str = " or ".join([f"<#{ch_id}>" for ch_id in ALLOWED_CHANNEL_IDS])
            await interaction.response.send_message(f"❌ This command can only be used in: {allowed_channels_str}", ephemeral=True)

    @wheelnames_cmd.error
    async def wheelnames_error(self, interaction, error): await self.handle_error(interaction, error)
    
    @wheel_cmd.error
    async def wheel_error(self, interaction, error): await self.handle_error(interaction, error)

    @reroll_cmd.error
    async def reroll_error(self, interaction, error): await self.handle_error(interaction, error)


async def setup(bot):
    await bot.add_cog(WheelCog(bot))
