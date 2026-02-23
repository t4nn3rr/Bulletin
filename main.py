import discord
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button, Select
import aiohttp
import json
import os
from datetime import datetime

# ─── CONFIG ───────────────────────────────────────────────────────────────────
WEBHOOK_URL = "https://discord.com/api/webhooks/1475369638001901761/juynubLrFgKHt9cG5E4tGCfj5DZdO5JDPdhu8pREGVEBEVxFCRZxYvwqisLTiyqfWxoa"
BOT_TOKEN   = os.getenv("DISCORD_BOT_TOKEN")
# ──────────────────────────────────────────────────────────────────────────────

# In-memory game storage: { game_id: { "show": ..., "open": bool, "entries": {user_id: {...}}, "answers": {...} } }
active_games: dict = {}

COLORS = {
    "🔵 Blue":    0x3498db,
    "🟢 Green":   0x2ecc71,
    "🔴 Red":     0xe74c3c,
    "🟡 Yellow":  0xf1c40f,
    "🟣 Purple":  0x9b59b6,
    "🟠 Orange":  0xe67e22,
    "⚪ White":   0xffffff,
    "⚫ Black":   0x2c2f33,
    "🩷 Pink":    0xff6b9d,
    "🩵 Cyan":    0x00d2d3,
}

# ═══════════════════════════════════════════════════════════════════════════════
#  BULLETIN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class BulletinModal(Modal, title="📋 Create Bulletin"):
    embed_title = TextInput(label="Title", placeholder="e.g. Server Announcement", max_length=256)
    description = TextInput(label="Description", placeholder="Main body of your bulletin...", style=discord.TextStyle.paragraph, max_length=4000)
    footer_text = TextInput(label="Footer", placeholder="e.g. Posted by Staff Team", required=False, max_length=2048)
    image_url   = TextInput(label="Image URL (optional)", placeholder="https://example.com/image.png", required=False)
    thumbnail_url = TextInput(label="Thumbnail URL (optional)", placeholder="https://example.com/thumb.png", required=False)

    def __init__(self, color: int = 0x3498db):
        super().__init__()
        self.chosen_color = color

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title=self.embed_title.value, description=self.description.value, color=self.chosen_color)
        if self.footer_text.value:
            embed.set_footer(text=self.footer_text.value)
        if self.image_url.value:
            embed.set_image(url=self.image_url.value)
        if self.thumbnail_url.value:
            embed.set_thumbnail(url=self.thumbnail_url.value)
        view = BulletinConfirmView(embed)
        await interaction.response.send_message("**📋 Preview — does this look good?**", embed=embed, view=view, ephemeral=True)

class ColorSelect(Select):
    def __init__(self):
        options = [discord.SelectOption(label=name, value=str(hex_val), description=f"#{hex_val:06X}") for name, hex_val in COLORS.items()]
        super().__init__(placeholder="🎨 Pick an embed color…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        color = int(self.values[0]) & 0xFFFFFF
        await interaction.response.send_modal(BulletinModal(color=color))

class ColorPickerView(View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(ColorSelect())

class BulletinConfirmView(View):
    def __init__(self, embed: discord.Embed):
        super().__init__(timeout=180)
        self.embed = embed

    @discord.ui.button(label="✅ Post Bulletin", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        success = await post_to_webhook(self.embed)
        msg = "✅ Bulletin posted!" if success else "❌ Failed to post. Check the webhook URL."
        await interaction.followup.send(msg, ephemeral=True)
        self.stop()

    @discord.ui.button(label="🗑️ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Bulletin cancelled.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="✏️ Edit Again", style=discord.ButtonStyle.secondary)
    async def edit(self, interaction: discord.Interaction, button: Button):
        color = self.embed.color.value if self.embed.color else 0x3498db
        await interaction.response.send_modal(BulletinModal(color=color))
        self.stop()

# ═══════════════════════════════════════════════════════════════════════════════
#  MASTERMIND — PLAYER MODALS (chained, 5 fields each)
# ═══════════════════════════════════════════════════════════════════════════════

class MastermindModal1(Modal, title="🌟 Eras Tour Bets — Outfits (1/3)"):
    lover_bodysuit    = TextInput(label="💗 Lover: The Man Jacket", placeholder="e.g. Pink sequin / No jacket", required=False)
    lover_guitar      = TextInput(label="💗 Lover: Guitar", placeholder="e.g. Heart guitar", required=False)
    fearless_dress    = TextInput(label="✨ Fearless: Fearless Dress", placeholder="e.g. Gold sparkle", required=False)
    red_shirt         = TextInput(label="❤️ Red: Red Shirt", placeholder="e.g. Classic red flannel", required=False)
    speaknow_gown     = TextInput(label="💜 Speak Now: Gown", placeholder="e.g. Purple ball gown", required=False)

    def __init__(self, game_id: str):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        if uid not in active_games[self.game_id]["entries"]:
            active_games[self.game_id]["entries"][uid] = {"user": str(interaction.user)}
        active_games[self.game_id]["entries"][uid].update({
            "lover_jacket":    self.lover_bodysuit.value,
            "lover_guitar":    self.lover_guitar.value,
            "fearless_dress":  self.fearless_dress.value,
            "red_shirt":       self.red_shirt.value,
            "speaknow_gown":   self.speaknow_gown.value,
        })
        await interaction.response.send_modal(MastermindModal2(self.game_id))

class MastermindModal2(Modal, title="🌟 Eras Tour Bets — Outfits (2/3)"):
    rep_bodysuit      = TextInput(label="🐍 reputation: Bodysuit", placeholder="e.g. Black snake bodysuit", required=False)
    folklore_dress    = TextInput(label="🌲 folklore: Dress", placeholder="e.g. Plaid cardigan dress", required=False)
    evermore_dress    = TextInput(label="🍂 evermore: Dress", placeholder="e.g. Brown/orange dress", required=False)
    _1989_top         = TextInput(label="☁️ 1989: Top", placeholder="e.g. Crop top", required=False)
    _1989_skirt       = TextInput(label="☁️ 1989: Skirt", placeholder="e.g. Sequin skirt", required=False)

    def __init__(self, game_id: str):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        active_games[self.game_id]["entries"][interaction.user.id].update({
            "rep_bodysuit":   self.rep_bodysuit.value,
            "folklore_dress": self.folklore_dress.value,
            "evermore_dress": self.evermore_dress.value,
            "1989_top":       self._1989_top.value,
            "1989_skirt":     self._1989_skirt.value,
        })
        await interaction.response.send_modal(MastermindModal3(self.game_id))

class MastermindModal3(Modal, title="🌟 Eras Tour Bets — Outfits (3/3)"):
    ttpd_dress        = TextInput(label="🩶 TTPD: Dress", placeholder="e.g. Grey/white dress", required=False)
    ttpd_bh_set       = TextInput(label="🩶 TTPD: Broken Heart Set", placeholder="e.g. Broken heart bodysuit", required=False)
    ttpd_bh_jacket    = TextInput(label="🩶 TTPD: Broken Heart Jacket", placeholder="e.g. Blazer jacket", required=False)
    midnights_shirt   = TextInput(label="🌙 Midnights: Shirt", placeholder="e.g. Glittery shirt", required=False)
    midnights_body    = TextInput(label="🌙 Midnights: Bodysuit", placeholder="e.g. Blue bodysuit", required=False)

    def __init__(self, game_id: str):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        active_games[self.game_id]["entries"][interaction.user.id].update({
            "ttpd_dress":      self.ttpd_dress.value,
            "ttpd_bh_set":     self.ttpd_bh_set.value,
            "ttpd_bh_jacket":  self.ttpd_bh_jacket.value,
            "midnights_shirt": self.midnights_shirt.value,
            "midnights_body":  self.midnights_body.value,
        })
        await interaction.response.send_modal(MastermindModal4(self.game_id))

class MastermindModal4(Modal, title="🌟 Eras Tour Bets — Songs & More (4/4)"):
    karma_jacket      = TextInput(label="🌙 Midnights: Karma Jacket", placeholder="e.g. Feather jacket", required=False)
    surprise_dress    = TextInput(label="🎸 Surprise Song Dress", placeholder="e.g. Floral dress", required=False)
    guitar_album      = TextInput(label="🎸 Guitar Surprise: Album", placeholder="e.g. folklore", required=False)
    guitar_song       = TextInput(label="🎸 Guitar Surprise: Song", placeholder="e.g. seven", required=False)
    piano_album       = TextInput(label="🎹 Piano Surprise: Album", placeholder="e.g. Red", required=False)

    def __init__(self, game_id: str):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        active_games[self.game_id]["entries"][interaction.user.id].update({
            "karma_jacket":   self.karma_jacket.value,
            "surprise_dress": self.surprise_dress.value,
            "guitar_album":   self.guitar_album.value,
            "guitar_song":    self.guitar_song.value,
            "piano_album":    self.piano_album.value,
        })
        await interaction.response.send_modal(MastermindModal5(self.game_id))

class MastermindModal5(Modal, title="🌟 Eras Tour Bets — Final Details (5/5)"):
    piano_song        = TextInput(label="🎹 Piano Surprise: Song", placeholder="e.g. All Too Well", required=False)
    special_guest     = TextInput(label="🌟 Special Guest", placeholder="e.g. Sabrina Carpenter / None", required=False)
    announcement      = TextInput(label="📢 Announcement", placeholder="e.g. New album / No announcement", required=False)
    setlist_change    = TextInput(label="📝 Setlist Change", placeholder="e.g. No changes / Added XYZ", required=False)
    notes             = TextInput(label="📌 Other Notes", placeholder="Anything else you want to predict!", required=False, style=discord.TextStyle.paragraph)

    def __init__(self, game_id: str):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        uid = interaction.user.id
        active_games[self.game_id]["entries"][uid].update({
            "piano_song":     self.piano_song.value,
            "special_guest":  self.special_guest.value,
            "announcement":   self.announcement.value,
            "setlist_change": self.setlist_change.value,
            "notes":          self.notes.value,
        })
        entry = active_games[self.game_id]["entries"][uid]
        show  = active_games[self.game_id]["show"]

        # Build confirmation embed
        embed = discord.Embed(
            title=f"✅ Bets Locked In — {show}",
            description=f"Your predictions have been submitted, {interaction.user.mention}! Good luck 🌟",
            color=0xff6b9d,
        )
        embed.add_field(name="💗 Lover", value=f"Jacket: {entry.get('lover_jacket') or '—'}\nGuitar: {entry.get('lover_guitar') or '—'}", inline=True)
        embed.add_field(name="✨ Fearless / ❤️ Red / 💜 Speak Now", value=f"Fearless Dress: {entry.get('fearless_dress') or '—'}\nRed Shirt: {entry.get('red_shirt') or '—'}\nSpeak Now Gown: {entry.get('speaknow_gown') or '—'}", inline=True)
        embed.add_field(name="🐍 rep / 🌲 folklore / 🍂 evermore", value=f"rep Bodysuit: {entry.get('rep_bodysuit') or '—'}\nfolklore Dress: {entry.get('folklore_dress') or '—'}\nevermore Dress: {entry.get('evermore_dress') or '—'}", inline=False)
        embed.add_field(name="☁️ 1989", value=f"Top: {entry.get('1989_top') or '—'}\nSkirt: {entry.get('1989_skirt') or '—'}", inline=True)
        embed.add_field(name="🩶 TTPD", value=f"Dress: {entry.get('ttpd_dress') or '—'}\nBH Set: {entry.get('ttpd_bh_set') or '—'}\nBH Jacket: {entry.get('ttpd_bh_jacket') or '—'}", inline=True)
        embed.add_field(name="🌙 Midnights", value=f"Shirt: {entry.get('midnights_shirt') or '—'}\nBodysuit: {entry.get('midnights_body') or '—'}\nKarma Jacket: {entry.get('karma_jacket') or '—'}", inline=False)
        embed.add_field(name="🎸 Guitar Surprise", value=f"Album: {entry.get('guitar_album') or '—'}\nSong: {entry.get('guitar_song') or '—'}", inline=True)
        embed.add_field(name="🎹 Piano Surprise", value=f"Album: {entry.get('piano_album') or '—'}\nSong: {entry.get('piano_song') or '—'}", inline=True)
        embed.add_field(name="🎤 Surprise Dress", value=entry.get('surprise_dress') or '—', inline=True)
        embed.add_field(name="🌟 Other", value=f"Guest: {entry.get('special_guest') or '—'}\nAnnouncement: {entry.get('announcement') or '—'}\nSetlist Change: {entry.get('setlist_change') or '—'}\nNotes: {entry.get('notes') or '—'}", inline=False)
        embed.set_footer(text=f"Submitted at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

        await interaction.response.send_message(embed=embed, ephemeral=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  MASTERMIND — PUBLIC GAME VIEW (the "Play Mastermind" button)
# ═══════════════════════════════════════════════════════════════════════════════

class MastermindGameView(View):
    def __init__(self, game_id: str):
        super().__init__(timeout=None)  # persistent
        self.game_id = game_id

    @discord.ui.button(label="🎯 Play Mastermind", style=discord.ButtonStyle.success, custom_id="play_mastermind")
    async def play(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ This game no longer exists.", ephemeral=True)
            return
        if not game["open"]:
            await interaction.response.send_message("🔒 This game is closed. No more submissions!", ephemeral=True)
            return
        if interaction.user.id in game["entries"]:
            await interaction.response.send_message("✅ You've already submitted your bets! Only one entry per person.", ephemeral=True)
            return
        await interaction.response.send_modal(MastermindModal1(self.game_id))

    @discord.ui.button(label="📊 View Entries", style=discord.ButtonStyle.secondary, custom_id="view_entries")
    async def view_entries(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ Game not found.", ephemeral=True)
            return
        count = len(game["entries"])
        names = ", ".join([v["user"] for v in game["entries"].values()]) or "Nobody yet"
        await interaction.response.send_message(f"**{count} player(s) have submitted bets:**\n{names}", ephemeral=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  MASTERMIND — ADMIN: CREATE GAME MODAL
# ═══════════════════════════════════════════════════════════════════════════════

class CreateGameModal(Modal, title="🌟 Create Mastermind Game"):
    show_name = TextInput(label="Show Name / Date", placeholder="e.g. Sydney Night 1 — Feb 23, 2024", max_length=100)
    description = TextInput(label="Description (shown to players)", placeholder="Place your bets before the show starts!", style=discord.TextStyle.paragraph, required=False)
    thumbnail = TextInput(label="Thumbnail Image URL (optional)", placeholder="https://example.com/eras.png", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        game_id = f"{interaction.guild_id}_{int(datetime.utcnow().timestamp())}"
        active_games[game_id] = {
            "show": self.show_name.value,
            "open": True,
            "entries": {},
            "answers": {},
            "channel_id": interaction.channel_id,
        }

        desc = self.description.value or "Think you know what Taylor will wear and play? Place your bets before the show starts! Click below to submit your predictions."

        embed = discord.Embed(
            title=f"🌟 Eras Tour Mastermind — {self.show_name.value}",
            description=desc,
            color=0xff6b9d,
        )
        embed.add_field(name="💗 Lover", value="The Man Jacket • Guitar", inline=True)
        embed.add_field(name="✨ Fearless / ❤️ Red / 💜 Speak Now", value="Fearless Dress • Red Shirt • Speak Now Gown", inline=True)
        embed.add_field(name="🐍 rep / 🌲 folklore / 🍂 evermore", value="rep Bodysuit • folklore Dress • evermore Dress", inline=False)
        embed.add_field(name="☁️ 1989", value="Top • Skirt", inline=True)
        embed.add_field(name="🩶 TTPD", value="Dress • Broken Heart Set • Broken Heart Jacket", inline=True)
        embed.add_field(name="🌙 Midnights", value="Shirt • Bodysuit • Karma Jacket", inline=False)
        embed.add_field(name="🎤 Surprise Songs", value="Dress • Guitar (Album + Song) • Piano (Album + Song)", inline=False)
        embed.add_field(name="🌟 Other", value="Special Guest • Announcement • Setlist Change • Notes", inline=False)
        embed.set_footer(text=f"Game ID: {game_id} • Submissions open")
        if self.thumbnail.value:
            embed.set_thumbnail(url=self.thumbnail.value)

        view = MastermindGameView(game_id)
        await interaction.response.send_message(embed=embed, view=view)

# ═══════════════════════════════════════════════════════════════════════════════
#  MASTERMIND — ADMIN: CLOSE + RESULTS MODAL
# ═══════════════════════════════════════════════════════════════════════════════

class CloseGameSelect(Select):
    def __init__(self, games: list):
        options = [discord.SelectOption(label=g["show"][:100], value=gid) for gid, g in games]
        super().__init__(placeholder="Select a game to close…", options=options)

    async def callback(self, interaction: discord.Interaction):
        gid = self.values[0]
        if gid in active_games:
            active_games[gid]["open"] = False
            await interaction.response.send_message(f"🔒 **{active_games[gid]['show']}** is now closed. No more submissions!", ephemeral=True)
        else:
            await interaction.response.send_message("Game not found.", ephemeral=True)

class CloseGameView(View):
    def __init__(self, games):
        super().__init__(timeout=60)
        self.add_item(CloseGameSelect(games))

class ViewEntriesSelect(Select):
    def __init__(self, games: list):
        options = [discord.SelectOption(label=g["show"][:100], value=gid) for gid, g in games]
        super().__init__(placeholder="Select a game to view entries…", options=options)

    async def callback(self, interaction: discord.Interaction):
        gid = self.values[0]
        game = active_games.get(gid)
        if not game:
            await interaction.response.send_message("Game not found.", ephemeral=True)
            return

        if not game["entries"]:
            await interaction.response.send_message("No entries yet.", ephemeral=True)
            return

        embeds = []
        for uid, entry in game["entries"].items():
            e = discord.Embed(title=f"📋 {entry['user']}", color=0xff6b9d)
            e.add_field(name="💗 Lover", value=f"Jacket: {entry.get('lover_jacket') or '—'}\nGuitar: {entry.get('lover_guitar') or '—'}", inline=True)
            e.add_field(name="✨/❤️/💜", value=f"Fearless: {entry.get('fearless_dress') or '—'}\nRed: {entry.get('red_shirt') or '—'}\nSpeak Now: {entry.get('speaknow_gown') or '—'}", inline=True)
            e.add_field(name="🐍/🌲/🍂", value=f"rep: {entry.get('rep_bodysuit') or '—'}\nfolklore: {entry.get('folklore_dress') or '—'}\nevermore: {entry.get('evermore_dress') or '—'}", inline=False)
            e.add_field(name="☁️ 1989", value=f"Top: {entry.get('1989_top') or '—'}\nSkirt: {entry.get('1989_skirt') or '—'}", inline=True)
            e.add_field(name="🩶 TTPD", value=f"Dress: {entry.get('ttpd_dress') or '—'}\nBH Set: {entry.get('ttpd_bh_set') or '—'}\nBH Jacket: {entry.get('ttpd_bh_jacket') or '—'}", inline=True)
            e.add_field(name="🌙 Midnights", value=f"Shirt: {entry.get('midnights_shirt') or '—'}\nBodysuit: {entry.get('midnights_body') or '—'}\nKarma Jacket: {entry.get('karma_jacket') or '—'}", inline=False)
            e.add_field(name="🎸 Guitar", value=f"{entry.get('guitar_album') or '—'} — {entry.get('guitar_song') or '—'}", inline=True)
            e.add_field(name="🎹 Piano", value=f"{entry.get('piano_album') or '—'} — {entry.get('piano_song') or '—'}", inline=True)
            e.add_field(name="🌟 Other", value=f"Guest: {entry.get('special_guest') or '—'}\nAnnouncement: {entry.get('announcement') or '—'}\nNotes: {entry.get('notes') or '—'}", inline=False)
            embeds.append(e)

        # Discord allows max 10 embeds per message
        await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)

class ViewEntriesView(View):
    def __init__(self, games):
        super().__init__(timeout=60)
        self.add_item(ViewEntriesSelect(games))

# ═══════════════════════════════════════════════════════════════════════════════
#  WEBHOOK SENDER
# ═══════════════════════════════════════════════════════════════════════════════

async def post_to_webhook(embed: discord.Embed) -> bool:
    payload = {"embeds": [embed.to_dict()]}
    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, data=json.dumps(payload), headers={"Content-Type": "application/json"}) as resp:
            return resp.status in (200, 204)

# ═══════════════════════════════════════════════════════════════════════════════
#  BOT SETUP
# ═══════════════════════════════════════════════════════════════════════════════

intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)

# ── /bulletin ──────────────────────────────────────────────────────────────────
@tree.command(name="bulletin", description="Create and post a bulletin embed")
@app_commands.choices(action=[app_commands.Choice(name="create", value="create")])
async def bulletin(interaction: discord.Interaction, action: app_commands.Choice[str]):
    if action.value == "create":
        await interaction.response.send_message("**📋 Bulletin Builder**\nFirst, pick a color:", view=ColorPickerView(), ephemeral=True)

# ── /mastermind ────────────────────────────────────────────────────────────────
mastermind_group = app_commands.Group(name="mastermind", description="Eras Tour Mastermind guessing game")

@mastermind_group.command(name="create", description="[Admin] Create a new Mastermind game for a show")
async def mastermind_create(interaction: discord.Interaction):
    await interaction.response.send_modal(CreateGameModal())

@mastermind_group.command(name="close", description="[Admin] Close submissions for a game")
async def mastermind_close(interaction: discord.Interaction):
    games = [(gid, g) for gid, g in active_games.items() if g.get("open")]
    if not games:
        await interaction.response.send_message("No open games found.", ephemeral=True)
        return
    await interaction.response.send_message("Select a game to close:", view=CloseGameView(games), ephemeral=True)

@mastermind_group.command(name="entries", description="[Admin] View all entries for a game")
async def mastermind_entries(interaction: discord.Interaction):
    games = list(active_games.items())
    if not games:
        await interaction.response.send_message("No games found.", ephemeral=True)
        return
    await interaction.response.send_message("Select a game:", view=ViewEntriesView(games), ephemeral=True)

@mastermind_group.command(name="list", description="List all active games")
async def mastermind_list(interaction: discord.Interaction):
    if not active_games:
        await interaction.response.send_message("No active games.", ephemeral=True)
        return
    lines = []
    for gid, g in active_games.items():
        status = "🟢 Open" if g["open"] else "🔴 Closed"
        lines.append(f"**{g['show']}** — {status} — {len(g['entries'])} entries")
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

tree.add_command(mastermind_group)

@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {client.user} — slash commands synced.")

client.run(BOT_TOKEN)
