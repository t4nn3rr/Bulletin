import discord
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button, Select
import aiohttp
import json
import os
from datetime import datetime, timezone

# ─── CONFIG ───────────────────────────────────────────────────────────────────
WEBHOOK_URL = "https://discord.com/api/webhooks/1475369638001901761/juynubLrFgKHt9cG5E4tGCfj5DZdO5JDPdhu8pREGVEBEVxFCRZxYvwqisLTiyqfWxoa"
BOT_TOKEN   = os.getenv("DISCORD_BOT_TOKEN")
# ──────────────────────────────────────────────────────────────────────────────

active_games: dict = {}

COLORS = {
    "🔵 Blue":   0x3498db, "🟢 Green":  0x2ecc71, "🔴 Red":    0xe74c3c,
    "🟡 Yellow": 0xf1c40f, "🟣 Purple": 0x9b59b6, "🟠 Orange": 0xe67e22,
    "⚪ White":  0xffffff, "⚫ Black":  0x2c2f33, "🩷 Pink":   0xff6b9d,
    "🩵 Cyan":   0x00d2d3,
}

OUTFIT_OPTIONS = {
    "lover_jacket": ["💛 Yellow Blazer", "🌈 Rhinestone Jacket", "💗 Pink Sequin Jacket", "🤍 White Jacket", "No Jacket"],
    "lover_guitar": ["💗 Heart Guitar", "🌈 Rainbow Guitar", "⭐ Star Guitar", "💛 Yellow Guitar", "🎸 Standard Guitar"],
    "fearless_dress": ["✨ Gold Sparkle Dress", "🤍 White Beaded Dress", "💛 Yellow Fringe Dress", "🌟 Silver Gown", "✨ Original Gold Gown"],
    "red_shirt": ["❤️ Classic Red Flannel", "🔴 Red Sequin Shirt", "🤍 White + Red Top", "🧣 Scarf Outfit", "❤️ Red Bodysuit"],
    "speaknow_gown": ["💜 Purple Ball Gown", "🌸 Lavender Gown", "💜 Purple Sequin Gown", "🤍 White + Purple Gown", "💜 Dark Purple Gown"],
    "rep_bodysuit": ["🐍 Black Snake Bodysuit", "⚡ Lightning Bolt Bodysuit", "🖤 Black Sequin Bodysuit", "🐍 Silver Snake Bodysuit", "🖤 Black Mesh Bodysuit"],
    "folklore_dress": ["🌲 Plaid Cardigan Dress", "🤍 White Cottagecore Dress", "🍄 Brown Midi Dress", "🌿 Green Plaid Dress", "🤍 Off-White Lace Dress"],
    "evermore_dress": ["🍂 Brown/Orange Ombre Dress", "🍁 Rust Plaid Dress", "🍂 Dark Brown Gown", "🌰 Chestnut Dress", "🍂 Burgundy Dress"],
    "1989_top": ["🩵 Blue Crop Top", "⭐ Sequin Crop Top", "🤍 White Crop Top", "☁️ Sky Blue Top", "💙 Cobalt Bedazzled Top"],
    "1989_skirt": ["🩵 Blue Sequin Skirt", "⭐ Silver Sparkle Skirt", "🤍 White Tulle Skirt", "☁️ Light Blue Mini Skirt", "💙 Cobalt Bedazzled Skirt"],
    "ttpd_dress": ["🩶 Grey Tulle Dress", "🤍 White Sheer Dress", "🩶 Silver Chain Dress", "🖤 Black + White Dress", "🩶 Dusty Grey Gown"],
    "ttpd_bh_set": ["🩶 Broken Heart Bodysuit + Skirt", "🤍 White BH Set", "🩶 Grey BH Coords", "💔 Black BH Bodysuit", "🩶 Silver BH Set"],
    "ttpd_bh_jacket": ["🩶 Grey Blazer", "🤍 White Oversized Blazer", "🖤 Black Blazer", "🩶 Silver Metallic Jacket", "No Jacket"],
    "midnights_shirt": ["🌙 Glittery Midnight Blue Shirt", "⭐ Star Print Shirt", "🌙 Navy Sequin Shirt", "🔮 Purple Glitter Shirt", "🌙 Dark Blue Bedazzled Shirt"],
    "midnights_body": ["🌙 Blue Sequin Bodysuit", "⭐ Silver Star Bodysuit", "🔮 Purple Bodysuit", "🌙 Navy Bodysuit", "⭐ Midnight Sparkle Bodysuit"],
    "karma_jacket": ["🪶 Feather Jacket", "🌙 Blue Feather Jacket", "⭐ Silver Feather Jacket", "🔮 Purple Feather Jacket", "No Jacket"],
    "surprise_dress": ["🌸 Floral Dress", "🤍 White Mini Dress", "✨ Sequin Mini Dress", "🌈 Colorful Dress", "🖤 Black Mini Dress", "💗 Pink Dress", "💛 Yellow Dress", "🩵 Blue Dress"],
    "special_guest": ["🎤 Sabrina Carpenter", "🎤 Gracie Abrams", "🎤 Muna", "🎤 Phoebe Bridgers", "🎤 Marcus Mumford", "🎤 Haim", "🎤 Ed Sheeran", "🎤 Ice Spice", "🎤 Paramore", "🎤 No Special Guest"],
    "announcement": ["💿 New Album Announcement", "🎬 Tour Extension", "🎥 New Music Video", "📺 TV Appearance / Special", "🏆 Award / Milestone", "📢 No Announcement"],
    "setlist_change": ["➕ Song Added", "➖ Song Removed", "🔄 Song Swapped", "📋 No Changes"],
}

# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def ensure_entry(game_id, uid, user_str):
    if uid not in active_games[game_id]["entries"]:
        active_games[game_id]["entries"][uid] = {"user": user_str}

def build_summary_embed(entry, show):
    e = discord.Embed(title=f"✅ Bets Locked — {show}", color=0xff6b9d, description="Your predictions are in! Good luck 🌟")
    e.add_field(name="💗 Lover", value=f"Jacket: {entry.get('lover_jacket','—')}\nGuitar: {entry.get('lover_guitar','—')}", inline=True)
    e.add_field(name="✨❤️💜 Fearless/Red/SN", value=f"Dress: {entry.get('fearless_dress','—')}\nShirt: {entry.get('red_shirt','—')}\nGown: {entry.get('speaknow_gown','—')}", inline=True)
    e.add_field(name="🐍🌲🍂 rep/folk/ever", value=f"rep: {entry.get('rep_bodysuit','—')}\nfolk: {entry.get('folklore_dress','—')}\never: {entry.get('evermore_dress','—')}", inline=False)
    e.add_field(name="☁️ 1989", value=f"Top: {entry.get('1989_top','—')}\nSkirt: {entry.get('1989_skirt','—')}", inline=True)
    e.add_field(name="🩶 TTPD", value=f"Dress: {entry.get('ttpd_dress','—')}\nBH Set: {entry.get('ttpd_bh_set','—')}\nBH Jacket: {entry.get('ttpd_bh_jacket','—')}", inline=True)
    e.add_field(name="🌙 Midnights", value=f"Shirt: {entry.get('midnights_shirt','—')}\nBodysuit: {entry.get('midnights_body','—')}\nKarma Jacket: {entry.get('karma_jacket','—')}", inline=False)
    e.add_field(name="🎤 Surprise Songs", value=f"Dress: {entry.get('surprise_dress','—')}\n🎸 {entry.get('guitar_album','—')} — {entry.get('guitar_song','—')}\n🎹 {entry.get('piano_album','—')} — {entry.get('piano_song','—')}", inline=False)
    e.add_field(name="🌟 Other", value=f"Guest: {entry.get('special_guest','—')}\nAnnouncement: {entry.get('announcement','—')}\nSetlist: {entry.get('setlist_change','—')}\nNotes: {entry.get('notes','—')}", inline=False)
    e.set_footer(text=f"Submitted {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    return e

# ═══════════════════════════════════════════════════════════════════════════════
#  GENERIC BET SELECT — each takes 1 row
# ═══════════════════════════════════════════════════════════════════════════════

class BetSelect(Select):
    def __init__(self, placeholder, key, game_id, uid, options):
        self.key = key
        self.game_id = game_id
        self.uid = uid
        super().__init__(placeholder=placeholder, options=[discord.SelectOption(label=o, value=o) for o in options], min_values=0, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return
        if self.values:
            active_games[self.game_id]["entries"][self.uid][self.key] = self.values[0]
        await interaction.response.defer()

# ═══════════════════════════════════════════════════════════════════════════════
#  STEP VIEWS
#  Discord limit: 5 rows per view. Each Select = 1 row, each Button row = 1 row.
#  Max 4 selects + 1 button row per view.
# ═══════════════════════════════════════════════════════════════════════════════

# STEP 1 — Lover (2 selects + 1 button = 3 rows) ✅
class Step1LoverView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("💛 The Man Jacket", "lover_jacket", game_id, uid, OUTFIT_OPTIONS["lover_jacket"]))
        self.add_item(BetSelect("🎸 Lover Guitar", "lover_guitar", game_id, uid, OUTFIT_OPTIONS["lover_guitar"]))

    @discord.ui.button(label="Next → Fearless / Red / Speak Now ›", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        entry = active_games[self.game_id]["entries"].get(self.uid, {})
        embed = discord.Embed(title="✨ Fearless / ❤️ Red / 💜 Speak Now", color=0xf1c40f,
                              description="**Step 2 of 8** — pick your outfit predictions.\n*All optional. Click Next when ready.*")
        embed.add_field(name="✅ Step 1 saved", value=f"Jacket: {entry.get('lover_jacket','—')}\nGuitar: {entry.get('lover_guitar','—')}", inline=False)
        await interaction.response.edit_message(embed=embed, view=Step2FearlessView(self.game_id, self.uid))


# STEP 2 — Fearless / Red / Speak Now (3 selects + 1 button = 4 rows) ✅
class Step2FearlessView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("✨ Fearless Dress", "fearless_dress", game_id, uid, OUTFIT_OPTIONS["fearless_dress"]))
        self.add_item(BetSelect("❤️ Red Shirt", "red_shirt", game_id, uid, OUTFIT_OPTIONS["red_shirt"]))
        self.add_item(BetSelect("💜 Speak Now Gown", "speaknow_gown", game_id, uid, OUTFIT_OPTIONS["speaknow_gown"]))

    @discord.ui.button(label="Next → rep / folklore / evermore ›", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="🐍 reputation / 🌲 folklore / 🍂 evermore", color=0x2c2f33,
                              description="**Step 3 of 8** — pick your outfit predictions.\n*All optional. Click Next when ready.*")
        await interaction.response.edit_message(embed=embed, view=Step3RepView(self.game_id, self.uid))


# STEP 3 — rep / folklore / evermore (3 selects + 1 button = 4 rows) ✅
class Step3RepView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("🐍 rep Bodysuit", "rep_bodysuit", game_id, uid, OUTFIT_OPTIONS["rep_bodysuit"]))
        self.add_item(BetSelect("🌲 folklore Dress", "folklore_dress", game_id, uid, OUTFIT_OPTIONS["folklore_dress"]))
        self.add_item(BetSelect("🍂 evermore Dress", "evermore_dress", game_id, uid, OUTFIT_OPTIONS["evermore_dress"]))

    @discord.ui.button(label="Next → 1989 ›", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="☁️ 1989", color=0x3498db,
                              description="**Step 4 of 8** — pick your 1989 outfit predictions.\n*All optional. Click Next when ready.*")
        await interaction.response.edit_message(embed=embed, view=Step4_1989View(self.game_id, self.uid))


# STEP 4 — 1989 (2 selects + 1 button = 3 rows) ✅
class Step4_1989View(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("☁️ 1989 Top", "1989_top", game_id, uid, OUTFIT_OPTIONS["1989_top"]))
        self.add_item(BetSelect("☁️ 1989 Skirt", "1989_skirt", game_id, uid, OUTFIT_OPTIONS["1989_skirt"]))

    @discord.ui.button(label="Next → TTPD ›", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="🩶 The Tortured Poets Department", color=0x708090,
                              description="**Step 5 of 8** — pick your TTPD outfit predictions.\n*All optional. Click Next when ready.*")
        await interaction.response.edit_message(embed=embed, view=Step5TTPDView(self.game_id, self.uid))


# STEP 5 — TTPD (3 selects + 1 button = 4 rows) ✅
class Step5TTPDView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("🩶 TTPD Dress", "ttpd_dress", game_id, uid, OUTFIT_OPTIONS["ttpd_dress"]))
        self.add_item(BetSelect("🩶 TTPD Broken Heart Set", "ttpd_bh_set", game_id, uid, OUTFIT_OPTIONS["ttpd_bh_set"]))
        self.add_item(BetSelect("🩶 TTPD Broken Heart Jacket", "ttpd_bh_jacket", game_id, uid, OUTFIT_OPTIONS["ttpd_bh_jacket"]))

    @discord.ui.button(label="Next → Midnights ›", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="🌙 Midnights", color=0x9b59b6,
                              description="**Step 6 of 8** — pick your Midnights predictions.\n*All optional. Click Next when ready.*")
        await interaction.response.edit_message(embed=embed, view=Step6MidnightsView(self.game_id, self.uid))


# STEP 6 — Midnights (3 selects + 1 button = 4 rows) ✅
class Step6MidnightsView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("🌙 Midnights Shirt", "midnights_shirt", game_id, uid, OUTFIT_OPTIONS["midnights_shirt"]))
        self.add_item(BetSelect("🌙 Midnights Bodysuit", "midnights_body", game_id, uid, OUTFIT_OPTIONS["midnights_body"]))
        self.add_item(BetSelect("🌙 Karma Jacket", "karma_jacket", game_id, uid, OUTFIT_OPTIONS["karma_jacket"]))

    @discord.ui.button(label="Next → Surprise Songs ›", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="🎤 Surprise Songs", color=0xe67e22,
                              description="**Step 7 of 8** — pick the surprise song dress, then enter your guitar & piano predictions.")
        await interaction.response.edit_message(embed=embed, view=Step7SurpriseView(self.game_id, self.uid))


# STEP 7 — Surprise Songs (1 select + 2 buttons = 3 rows) ✅
class SurpriseSongsModal(Modal, title="🎸🎹 Surprise Song Predictions"):
    guitar_album = TextInput(label="🎸 Guitar: Album", placeholder="e.g. folklore", required=False, max_length=50)
    guitar_song  = TextInput(label="🎸 Guitar: Song Title", placeholder="e.g. seven", required=False, max_length=100)
    piano_album  = TextInput(label="🎹 Piano: Album", placeholder="e.g. Red (TV)", required=False, max_length=50)
    piano_song   = TextInput(label="🎹 Piano: Song Title", placeholder="e.g. All Too Well (10 Min)", required=False, max_length=100)

    def __init__(self, game_id, uid):
        super().__init__()
        self.game_id = game_id; self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        active_games[self.game_id]["entries"][self.uid].update({
            "guitar_album": self.guitar_album.value or "—",
            "guitar_song":  self.guitar_song.value or "—",
            "piano_album":  self.piano_album.value or "—",
            "piano_song":   self.piano_song.value or "—",
        })
        await interaction.response.send_message("🎸🎹 Songs saved! Click **Next → Other Predictions** to continue.", ephemeral=True)

class Step7SurpriseView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("🎤 Surprise Song Dress", "surprise_dress", game_id, uid, OUTFIT_OPTIONS["surprise_dress"]))

    @discord.ui.button(label="🎸🎹 Enter Guitar & Piano Songs", style=discord.ButtonStyle.secondary, row=1)
    async def songs_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        await interaction.response.send_modal(SurpriseSongsModal(self.game_id, self.uid))

    @discord.ui.button(label="Next → Other Predictions ›", style=discord.ButtonStyle.primary, row=1)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="🌟 Other Predictions", color=0x2ecc71,
                              description="**Step 8 of 8** — final picks! Submit when done.")
        await interaction.response.edit_message(embed=embed, view=Step8OtherView(self.game_id, self.uid))


# STEP 8 — Other (3 selects + 2 buttons = 5 rows) ✅
class NotesModal(Modal, title="📌 Extra Notes"):
    notes = TextInput(label="Notes", placeholder="Any other predictions or comments...",
                      style=discord.TextStyle.paragraph, required=False, max_length=500)

    def __init__(self, game_id, uid):
        super().__init__()
        self.game_id = game_id; self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        active_games[self.game_id]["entries"][self.uid]["notes"] = self.notes.value or "—"
        await interaction.response.send_message("📌 Notes saved!", ephemeral=True)

class Step8OtherView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("🌟 Special Guest", "special_guest", game_id, uid, OUTFIT_OPTIONS["special_guest"]))
        self.add_item(BetSelect("📢 Announcement", "announcement", game_id, uid, OUTFIT_OPTIONS["announcement"]))
        self.add_item(BetSelect("📝 Setlist Change", "setlist_change", game_id, uid, OUTFIT_OPTIONS["setlist_change"]))

    @discord.ui.button(label="📌 Add Notes (optional)", style=discord.ButtonStyle.secondary, row=4)
    async def notes_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        await interaction.response.send_modal(NotesModal(self.game_id, self.uid))

    @discord.ui.button(label="🔒 Submit My Bets!", style=discord.ButtonStyle.success, row=4)
    async def submit_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        entry = active_games[self.game_id]["entries"].get(self.uid, {})
        show  = active_games[self.game_id]["show"]
        embed = build_summary_embed(entry, show)
        await interaction.response.edit_message(content="✅ **Your bets are locked in!**", embed=embed, view=None)


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC GAME VIEW
# ═══════════════════════════════════════════════════════════════════════════════

class MastermindGameView(View):
    def __init__(self, game_id):
        super().__init__(timeout=None)
        self.game_id = game_id

    @discord.ui.button(label="🎯 Play Mastermind", style=discord.ButtonStyle.success)
    async def play(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("❌ This game no longer exists.", ephemeral=True); return
        if not game["open"]:
            await interaction.response.send_message("🔒 Submissions are closed!", ephemeral=True); return
        if interaction.user.id in game["entries"]:
            await interaction.response.send_message("✅ You've already submitted your bets!", ephemeral=True); return
        uid = interaction.user.id
        ensure_entry(self.game_id, uid, str(interaction.user))
        embed = discord.Embed(title=f"💗 Lover Era — {game['show']}",
                              description="**Step 1 of 8** — pick your Lover era outfit predictions.\n*All fields optional. Click Next when ready.*",
                              color=0xff6b9d)
        await interaction.response.send_message(embed=embed, view=Step1LoverView(self.game_id, uid), ephemeral=True)

    @discord.ui.button(label="👥 Entry Count", style=discord.ButtonStyle.secondary)
    async def count(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("Game not found.", ephemeral=True); return
        await interaction.response.send_message(f"**{len(game['entries'])} player(s)** have submitted bets!", ephemeral=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN — CREATE GAME
# ═══════════════════════════════════════════════════════════════════════════════

class CreateGameModal(Modal, title="🌟 Create Mastermind Game"):
    show_name   = TextInput(label="Show Name / Date", placeholder="e.g. Sydney Night 1 — Feb 23, 2024", max_length=100)
    description = TextInput(label="Description", placeholder="Place your bets before the show!", style=discord.TextStyle.paragraph, required=False)
    thumbnail   = TextInput(label="Thumbnail Image URL (optional)", placeholder="https://example.com/eras.png", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        game_id = f"{interaction.guild_id}_{int(datetime.now(timezone.utc).timestamp())}"
        active_games[game_id] = {"show": self.show_name.value, "open": True, "entries": {}}
        desc = self.description.value or "Think you know what Taylor will wear and play? Place your bets before the show starts!"
        embed = discord.Embed(title=f"🌟 Eras Tour Mastermind — {self.show_name.value}", description=desc, color=0xff6b9d)
        embed.add_field(name="💗 Lover", value="The Man Jacket • Guitar", inline=True)
        embed.add_field(name="✨❤️💜 Fearless / Red / SN", value="Fearless Dress • Red Shirt • Speak Now Gown", inline=True)
        embed.add_field(name="🐍🌲🍂 rep / folklore / evermore", value="rep Bodysuit • folklore Dress • evermore Dress", inline=False)
        embed.add_field(name="☁️ 1989", value="Top • Skirt", inline=True)
        embed.add_field(name="🩶 TTPD", value="Dress • Broken Heart Set • Broken Heart Jacket", inline=True)
        embed.add_field(name="🌙 Midnights", value="Shirt • Bodysuit • Karma Jacket", inline=False)
        embed.add_field(name="🎤 Surprise Songs", value="Dress • 🎸 Guitar (Album + Song) • 🎹 Piano (Album + Song)", inline=False)
        embed.add_field(name="🌟 Other", value="Special Guest • Announcement • Setlist Change • Notes", inline=False)
        embed.set_footer(text="Click 🎯 Play Mastermind to place your bets!")
        if self.thumbnail.value:
            embed.set_thumbnail(url=self.thumbnail.value)
        await interaction.response.send_message(embed=embed, view=MastermindGameView(game_id))


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN — CLOSE / VIEW ENTRIES
# ═══════════════════════════════════════════════════════════════════════════════

class CloseGameSelect(Select):
    def __init__(self, games):
        super().__init__(placeholder="Select a game to close…",
                         options=[discord.SelectOption(label=g["show"][:100], value=gid) for gid, g in games])

    async def callback(self, interaction: discord.Interaction):
        gid = self.values[0]
        active_games[gid]["open"] = False
        await interaction.response.send_message(f"🔒 **{active_games[gid]['show']}** is now closed.", ephemeral=True)

class CloseGameView(View):
    def __init__(self, games):
        super().__init__(timeout=60)
        self.add_item(CloseGameSelect(games))

class ViewEntriesSelect(Select):
    def __init__(self, games):
        super().__init__(placeholder="Select a game…",
                         options=[discord.SelectOption(label=g["show"][:100], value=gid) for gid, g in games])

    async def callback(self, interaction: discord.Interaction):
        gid = self.values[0]
        game = active_games.get(gid)
        if not game or not game["entries"]:
            await interaction.response.send_message("No entries yet.", ephemeral=True); return
        embeds = [build_summary_embed(e, game["show"]) for e in list(game["entries"].values())[:10]]
        await interaction.response.send_message(embeds=embeds, ephemeral=True)

class ViewEntriesView(View):
    def __init__(self, games):
        super().__init__(timeout=60)
        self.add_item(ViewEntriesSelect(games))


# ═══════════════════════════════════════════════════════════════════════════════
#  BULLETIN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class BulletinModal(Modal, title="📋 Create Bulletin"):
    embed_title   = TextInput(label="Title", placeholder="e.g. Server Announcement", max_length=256)
    description   = TextInput(label="Description", placeholder="Main body...", style=discord.TextStyle.paragraph, max_length=4000)
    footer_text   = TextInput(label="Footer", placeholder="e.g. Posted by Staff Team", required=False, max_length=2048)
    image_url     = TextInput(label="Image URL (optional)", placeholder="https://example.com/image.png", required=False)
    thumbnail_url = TextInput(label="Thumbnail URL (optional)", required=False)

    def __init__(self, color=0x3498db):
        super().__init__()
        self.chosen_color = color

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(title=self.embed_title.value, description=self.description.value, color=self.chosen_color)
        if self.footer_text.value:   embed.set_footer(text=self.footer_text.value)
        if self.image_url.value:     embed.set_image(url=self.image_url.value)
        if self.thumbnail_url.value: embed.set_thumbnail(url=self.thumbnail_url.value)
        await interaction.response.send_message("**📋 Preview:**", embed=embed, view=BulletinConfirmView(embed), ephemeral=True)

class ColorSelect(Select):
    def __init__(self):
        super().__init__(placeholder="🎨 Pick a color…",
                         options=[discord.SelectOption(label=n, value=str(v), description=f"#{v:06X}") for n, v in COLORS.items()])

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(BulletinModal(color=int(self.values[0]) & 0xFFFFFF))

class ColorPickerView(View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(ColorSelect())

class BulletinConfirmView(View):
    def __init__(self, embed):
        super().__init__(timeout=180)
        self.embed = embed

    @discord.ui.button(label="✅ Post", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        ok = await post_to_webhook(self.embed)
        await interaction.followup.send("✅ Posted!" if ok else "❌ Failed.", ephemeral=True)

    @discord.ui.button(label="🗑️ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Cancelled.", ephemeral=True)

    @discord.ui.button(label="✏️ Edit", style=discord.ButtonStyle.secondary)
    async def edit(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(BulletinModal(color=self.embed.color.value if self.embed.color else 0x3498db))


# ═══════════════════════════════════════════════════════════════════════════════
#  WEBHOOK + BOT
# ═══════════════════════════════════════════════════════════════════════════════

async def post_to_webhook(embed):
    payload = {"embeds": [embed.to_dict()]}
    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, data=json.dumps(payload),
                                headers={"Content-Type": "application/json"}) as resp:
            return resp.status in (200, 204)

intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)

@tree.command(name="bulletin", description="Create and post a bulletin embed")
@app_commands.choices(action=[app_commands.Choice(name="create", value="create")])
async def bulletin(interaction: discord.Interaction, action: app_commands.Choice[str]):
    await interaction.response.send_message("**📋 Bulletin Builder** — pick a color:", view=ColorPickerView(), ephemeral=True)

mastermind_group = app_commands.Group(name="mastermind", description="Eras Tour Mastermind guessing game")

@mastermind_group.command(name="create", description="[Admin] Create a new Mastermind game for a show")
async def mastermind_create(interaction: discord.Interaction):
    await interaction.response.send_modal(CreateGameModal())

@mastermind_group.command(name="close", description="[Admin] Close submissions for a game")
async def mastermind_close(interaction: discord.Interaction):
    games = [(gid, g) for gid, g in active_games.items() if g.get("open")]
    if not games:
        await interaction.response.send_message("No open games.", ephemeral=True); return
    await interaction.response.send_message("Select a game to close:", view=CloseGameView(games), ephemeral=True)

@mastermind_group.command(name="entries", description="[Admin] View all entries for a game")
async def mastermind_entries(interaction: discord.Interaction):
    if not active_games:
        await interaction.response.send_message("No games found.", ephemeral=True); return
    await interaction.response.send_message("Select a game:", view=ViewEntriesView(list(active_games.items())), ephemeral=True)

@mastermind_group.command(name="list", description="List all active games and entry counts")
async def mastermind_list(interaction: discord.Interaction):
    if not active_games:
        await interaction.response.send_message("No active games.", ephemeral=True); return
    lines = [f"**{g['show']}** — {'🟢 Open' if g['open'] else '🔴 Closed'} — {len(g['entries'])} entries" for g in active_games.values()]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

tree.add_command(mastermind_group)

@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {client.user} — slash commands synced.")

client.run(BOT_TOKEN)
