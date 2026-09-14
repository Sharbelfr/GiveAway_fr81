import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import checks, MissingAnyRole
import random
import asyncio
import aiosqlite
import datetime

# 🔴 إعدادات البوت الأساسية 🔴
# ضع آيديات الرومات المسموحة هنا بين الأقواس، افصل بين كل آيدي بفاصلة
ALLOWED_CHANNEL_IDS = [1549031641660526753, 1548116799529422970] 
# يمكنك كتابة اسم الرتبة بين علامات تنصيص " " أو كتابة الآيدي كرقم مباشر. افصل بينها بفاصلة.
ALLOWED_ROLES = ["Giveaway host", "Admin", 123456789012345678] 

# أداة التحقق من الرومات المتعددة
def in_allowed_channels():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.channel_id in ALLOWED_CHANNEL_IDS
    return app_commands.check(predicate)

# ==========================================
# 1. نظام السحب اليدوي (أسماء مخصصة)
# ==========================================
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


class WheelNamesModal(discord.ui.Modal, title='Manual Giveaway Details'):
    prize = discord.ui.TextInput(label='Prize', placeholder='What is the prize?', required=True)
    names = discord.ui.TextInput(label='Participants', style=discord.TextStyle.paragraph, placeholder='Alex, Mike, Sarah (comma separated)', required=True)

    async def on_submit(self, interaction: discord.Interaction):
        names_list = [name.strip() for name in self.names.value.split(",") if name.strip()]
        if len(names_list) < 2:
            await interaction.response.send_message("❌ Please provide at least 2 names.", ephemeral=True)
            return

        async with aiosqlite.connect("giveaways.db") as db:
            cursor = await db.execute("INSERT INTO giveaways (host_id, prize, status) VALUES (?, ?, 'active')", 
                                      (interaction.user.id, self.prize.value))
            giveaway_id = cursor.lastrowid
            await db.commit()

        participants_list = "\n".join(f"• {name}" for name in names_list)
        embed = discord.Embed(
            title="ZYNR",
            description=f"**Prize:** {self.prize.value}\n**Hosted by:** {interaction.user.mention}\n\n**Participants:**\n{participants_list}",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Made by SharbelFr81")
        view = WheelNamesView(interaction.user.id, names_list, giveaway_id, self.prize.value)
        await interaction.response.send_message(embed=embed, view=view)


# ==========================================
# 2. نظام السحب التفاعلي (العداد الزمني التلقائي)
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

    @discord.ui.button(label="Join Giveaway 🎉", style=discord.ButtonStyle.success, emoji="🎟️")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.mention in self.participants:
            await interaction.response.send_message("✅ You have already joined this giveaway!", ephemeral=True)
            return
        
        self.participants.append(interaction.user.mention)
        await interaction.response.send_message("🎉 You have successfully joined the giveaway!", ephemeral=True)
        
        embed = interaction.message.embeds[0]
        embed.description = f"**Prize:** {self.prize}\n**Hosted by:** <@{self.host_id}>\n**Ends:** <t:{self.end_timestamp}:R>\n\n**Current Participants:** {len(self.participants)}"
        await interaction.message.edit(embed=embed)

    async def auto_end_giveaway(self):
        if not self.message: return

        for child in self.children:
            child.disabled = True

        if len(self.participants) == 0:
            embed_cancel = discord.Embed(
                title="ZYNR - ❌ Giveaway Cancelled",
                description=f"**Prize:** {self.prize}\n\nNo one joined the giveaway.",
                color=discord.Color.red()
            )
            embed_cancel.set_footer(text="Made by SharbelFr81")
            await self.message.edit(embed=embed_cancel, view=self)
            return

        winner = random.choice(self.participants)
        
        embed_spinning = discord.Embed(
            title="ZYNR",
            description=f"**Prize:** {self.prize}\n\n🎡 Spinning the wheel...",
            color=discord.Color.gold()
        )
        embed_spinning.set_footer(text="Made by SharbelFr81")
        await self.message.edit(embed=embed_spinning, view=self)
        
        await asyncio.sleep(2)
        
        embed_result = discord.Embed(
            title="ZYNR - 🎉 Giveaway Result!",
            description=f"**Prize:** {self.prize}\n\n🏆 The winner is: **{winner}** 🏆\n\nCongratulations!",
            color=discord.Color.green()
        )
        embed_result.set_footer(text="Made by SharbelFr81")
        
        await self.message.edit(embed=embed_result, view=None)
        await self.message.channel.send(f"🎉 **{winner}** won **{self.prize}**! (Hosted by: <@{self.host_id}>)")

        async with aiosqlite.connect("giveaways.db") as db:
            await db.execute("UPDATE giveaways SET winner = ?, status = 'closed' WHERE id = ?", (winner, self.giveaway_id))
            await db.commit()


class InteractiveGiveawayModal(discord.ui.Modal, title='Timed Giveaway Details'):
    prize = discord.ui.TextInput(label='Prize', placeholder='What is the prize?', required=True)
    duration = discord.ui.TextInput(label='Duration (in minutes)', placeholder='e.g. 10', required=True, max_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            minutes = int(self.duration.value)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number for minutes.", ephemeral=True)
            return

        end_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
        unix_timestamp = int(end_time.timestamp())

        async with aiosqlite.connect("giveaways.db") as db:
            cursor = await db.execute("INSERT INTO giveaways (host_id, prize, status) VALUES (?, ?, 'active')", 
                                      (interaction.user.id, self.prize.value))
            giveaway_id = cursor.lastrowid
            await db.commit()

        embed = discord.Embed(
            title="ZYNR",
            description=f"**Prize:** {self.prize.value}\n**Hosted by:** {interaction.user.mention}\n**Ends:** <t:{unix_timestamp}:R>\n\n**Current Participants:** 0",
            color=discord.Color.blue()
        )
        embed.set_footer(text="Made by SharbelFr81")

        view = InteractiveGiveawayView(interaction.user.id, giveaway_id, self.prize.value, unix_timestamp)
        await interaction.response.send_message(embed=embed, view=view)
        
        view.message = await interaction.original_response()
        await asyncio.sleep(minutes * 60)
        await view.auto_end_giveaway()


# ==========================================
# 3. الكوج والأوامر الرئيسية
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
                                winner TEXT)''')
            await db.commit()

    @app_commands.command(name="wheelnames", description="Create a manual name raffle with a UI Modal")
    @checks.has_any_role(*ALLOWED_ROLES)
    @in_allowed_channels()
    async def wheelnames_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_modal(WheelNamesModal())

    @wheelnames_cmd.error
    async def wheelnames_error(self, interaction: discord.Interaction, error):
        if isinstance(error, MissingAnyRole):
            await interaction.response.send_message("❌ You do not have the required role to host a giveaway!", ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure):
            # دمج الرومات في رسالة الخطأ ليظهروا كـ منشن
            allowed_channels_str = " or ".join([f"<#{ch_id}>" for ch_id in ALLOWED_CHANNEL_IDS])
            await interaction.response.send_message(f"❌ This command can only be used in {allowed_channels_str}!", ephemeral=True)

    @app_commands.command(name="wheel", description="Create a timed auto-draw giveaway with a UI Modal")
    @checks.has_any_role(*ALLOWED_ROLES)
    @in_allowed_channels()
    async def wheel_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_modal(InteractiveGiveawayModal())

    @wheel_cmd.error
    async def wheel_error(self, interaction: discord.Interaction, error):
        if isinstance(error, MissingAnyRole):
            await interaction.response.send_message("❌ You do not have the required role to host a giveaway!", ephemeral=True)
        elif isinstance(error, app_commands.CheckFailure):
            allowed_channels_str = " or ".join([f"<#{ch_id}>" for ch_id in ALLOWED_CHANNEL_IDS])
            await interaction.response.send_message(f"❌ This command can only be used in {allowed_channels_str}!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(WheelCog(bot))
