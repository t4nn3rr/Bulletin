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
    "Blue":   0x3498db, "Green":  0x2ecc71, "Red":    0xe74c3c,
    "Yellow": 0xf1c40f, "Purple": 0x9b59b6, "Orange": 0xe67e22,
    "White":  0xffffff, "Black":  0x2c2f33, "Pink":   0xff6b9d,
    "Cyan":   0x00d2d3,
}

# All scorable fields and their display labels
SCORE_FIELDS = [
    ("lover_bodysuit",  "Lover Bodysuit"),
    ("lover_jacket",    "Lover Jacket"),
    ("lover_guitar",    "Lover Guitar"),
    ("fearless_dress",  "Fearless Dress"),
    ("red_shirt",       "Red Shirt"),
    ("speaknow_dress",  "Speak Now Dress"),
    ("rep_bodysuit",    "rep Bodysuit"),
    ("folklore_dress",  "folklore Dress"),
    ("1989_combo",      "1989 Combo"),
    ("1989_top",        "1989 Top"),
    ("1989_skirt",      "1989 Skirt"),
    ("ttpd_dress",      "TTPD Dress"),
    ("ttpd_set",        "TTPD Set"),
    ("ttpd_jacket",     "TTPD Jacket/Cape"),
    ("midnights_shirt", "Midnights Shirt Dress"),
    ("midnights_body",  "Midnights Bodysuit"),
    ("karma_jacket",    "Karma Jacket"),
    ("surprise_dress",  "Surprise Song Dress"),
    ("guitar_album",    "Guitar Surprise Album"),
    ("guitar_song",     "Guitar Surprise Song"),
    ("piano_album",     "Piano Surprise Album"),
    ("piano_song",      "Piano Surprise Song"),
    ("special_guest",   "Special Guest"),
    ("setlist_change",  "Setlist Change"),
]

OUTFIT_OPTIONS = {
    "lover_bodysuit": ["Pink & Blue bodysuit", "Gold & Blue bodysuit", "Purple bodysuit", "Pink bodysuit", "Tangerine (orange) bodysuit"],
    "lover_jacket":   ["Silver The Man jacket", "Black The Man jacket", "Purple The Man jacket", "Pink The Man jacket", "Tangerine The Man jacket"],
    "lover_guitar":   ["Pink guitar", "Blue guitar", "Lavender guitar"],
    "fearless_dress": ["Short gold", "Long gold", "Long silver", "Black & Silver"],
    "red_shirt":      ["A lot going on", "Ew", "Like ever", "Taylor's version", "About me", "Trouble"],
    "speaknow_dress": ["Champagne dress", "Pink dress", "Tissue paper dress", "Silver dress", "Purple dress", "Blue dress", "Swirls dress"],
    "rep_bodysuit":   ["Black & Red"],
    "folklore_dress": ["Purple dress", "Cream dress", "Pink dress", "Green dress", "Blue dress", "Yellow dress", "Berry dress"],
    "1989_combo": [
        "Pink, Blue - Mermaid", "Orange, Purple - Tutti Frutti", "Green, Pink - Watermelon",
        "Yellow, Orange - Chiefs", "Yellow, Blue - Swedish Fish", "Pink, Orange - Starburst",
        "Blue, Yellow - Flounder", "Purple, Blue - Sully", "Pink, Yellow - Pink Lemonade",
        "Orange, Yellow - Fuego", "Pink, Purple - Cheshire Cat", "Fully Orange - Karma",
        "Green, Blue - Debut", "Yellow, Pink - Princess Peach", "Blue, Purple - Bibble",
        "Purple, Green - Ariel", "Blue, Pink - Loverpool", "Purple, Orange - Tide Pod",
        "Yellow, Green - Lemon Lime", "Orange, Blue - Fundon", "Purple, Pink - Purple Pink Skies",
        "Pink, Green - Cosmo & Wanda", "Orange, Pink - 2016 Grammys", "Green, Purple - Tayhulk",
        "Blue, Orange - Firecracker",
    ],
    "1989_combo_b": [
        "Green, Orange - Taycarrot", "Yellow, Purple - Rapunzel", "Orange, Green - The Lucky One",
    ],
    "1989_top":        ["Orange top", "Green top", "Blue top", "Yellow top", "Pink top", "Purple top"],
    "1989_skirt":      ["Orange skirt", "Green skirt", "Blue skirt", "Yellow skirt", "Pink skirt", "Purple skirt"],
    "ttpd_dress":      ["White dress"],
    "ttpd_set":        ["Black", "White", "Graphite"],
    "ttpd_jacket":     ["Gold", "White", "Graphite", "Silver"],
    "surprise_dress":  ["Bright pink", "Ocean blue", "Sunset (orange)"],
    "midnights_shirt": ["Dark purple", "Bright blue", "Silver", "Pink", "Light purple", "Iridescent"],
    "midnights_body":  ["Dark blue", "Scallops", "Cutouts", "Chevron"],
    "karma_jacket":    ["Multicolor", "Magenta", "Blue", "Pink", "No jacket"],
    "special_guest":   ["Sabrina Carpenter", "Gracie Abrams", "Muna", "Phoebe Bridgers", "Marcus Mumford", "Haim", "Ed Sheeran", "Ice Spice", "Paramore", "No Special Guest"],
    "announcement":    ["New Album Announcement", "Tour Extension", "New Music Video", "TV Appearance / Special", "Award / Milestone", "No Announcement"],
    "setlist_change":  ["Song Added", "Song Removed", "Song Swapped", "No Changes"],
}

# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def ensure_entry(game_id, uid, user_str):
    if uid not in active_games[game_id]["entries"]:
        active_games[game_id]["entries"][uid] = {"user": user_str}

def score_entry(entry, answers):
    """Return (points, total_possible, per_field dict)."""
    results = {}
    points = 0
    possible = 0
    for key, label in SCORE_FIELDS:
        answer = answers.get(key, "").strip().lower()
        guess  = entry.get(key, "").strip().lower()
        if not answer:
            continue
        possible += 1
        correct = (answer == guess) or (answer in guess) or (guess in answer)
        if correct:
            points += 1
        results[key] = {"label": label, "guess": entry.get(key, "—"), "answer": answers.get(key, "—"), "correct": correct}
    return points, possible, results

def build_summary_embed(entry, show):
    e = discord.Embed(title=f"Bets Locked — {show}", color=0x5865f2,
                      description=f"Submitted by {entry.get('user', 'Unknown')}")
    e.add_field(name="Lover",
                value=f"Bodysuit: {entry.get('lover_bodysuit','—')}\nJacket: {entry.get('lover_jacket','—')}\nGuitar: {entry.get('lover_guitar','—')}", inline=False)
    e.add_field(name="Fearless / Red / Speak Now",
                value=f"Fearless: {entry.get('fearless_dress','—')}\nRed Shirt: {entry.get('red_shirt','—')}\nSpeak Now: {entry.get('speaknow_dress','—')}", inline=False)
    e.add_field(name="rep / folklore",
                value=f"rep Bodysuit: {entry.get('rep_bodysuit','—')}\nfolklore Dress: {entry.get('folklore_dress','—')}", inline=False)
    e.add_field(name="1989",
                value=f"Combo: {entry.get('1989_combo','—')}\nTop: {entry.get('1989_top','—')}\nSkirt: {entry.get('1989_skirt','—')}", inline=False)
    e.add_field(name="TTPD",
                value=f"Dress: {entry.get('ttpd_dress','—')}\nSet: {entry.get('ttpd_set','—')}\nJacket/Cape: {entry.get('ttpd_jacket','—')}", inline=False)
    e.add_field(name="Midnights",
                value=f"Shirt Dress: {entry.get('midnights_shirt','—')}\nBodysuit: {entry.get('midnights_body','—')}\nKarma Jacket: {entry.get('karma_jacket','—')}", inline=False)
    e.add_field(name="Surprise Songs",
                value=f"Dress: {entry.get('surprise_dress','—')}\nGuitar: {entry.get('guitar_album','—')} — {entry.get('guitar_song','—')}\nPiano: {entry.get('piano_album','—')} — {entry.get('piano_song','—')}", inline=False)
    e.add_field(name="Other",
                value=f"Guest: {entry.get('special_guest','—')}\nSetlist: {entry.get('setlist_change','—')}\nNotes: {entry.get('notes','—')}", inline=False)
    e.set_footer(text=f"Submitted {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    return e

def build_score_embed(entry, answers, show):
    points, possible, results = score_entry(entry, answers)
    pct = round((points / possible) * 100) if possible else 0
    e = discord.Embed(
        title=f"Results — {entry.get('user', 'Unknown')}",
        description=f"**{points} / {possible} correct ({pct}%)**",
        color=0x2ecc71 if pct >= 70 else (0xf1c40f if pct >= 40 else 0xe74c3c)
    )
    correct_lines = []
    wrong_lines   = []
    skipped_lines = []
    for key, label in SCORE_FIELDS:
        if key not in results:
            skipped_lines.append(f"{label}: {entry.get(key, '—')}")
        elif results[key]["correct"]:
            correct_lines.append(f"{label}: {results[key]['guess']}")
        else:
            wrong_lines.append(f"{label}: guessed **{results[key]['guess']}**, answer **{results[key]['answer']}**")
    if correct_lines:
        e.add_field(name=f"Correct ({len(correct_lines)})", value="\n".join(correct_lines) or "None", inline=False)
    if wrong_lines:
        e.add_field(name=f"Wrong ({len(wrong_lines)})", value="\n".join(wrong_lines) or "None", inline=False)
    if skipped_lines:
        e.add_field(name="Not answered / not scored", value="\n".join(skipped_lines[:10]) or "None", inline=False)
    return e, points, possible

def build_leaderboard_embed(game):
    answers = game.get("answers", {})
    show = game["show"]
    scores = []
    for uid, entry in game["entries"].items():
        pts, possible, _ = score_entry(entry, answers)
        scores.append((entry.get("user", str(uid)), pts, possible))
    scores.sort(key=lambda x: x[1], reverse=True)

    e = discord.Embed(title=f"Leaderboard — {show}", color=0x5865f2)
    if not scores:
        e.description = "No entries yet."
        return e
    lines = []
    medals = ["1st", "2nd", "3rd"]
    for i, (user, pts, possible) in enumerate(scores):
        rank = medals[i] if i < 3 else f"{i+1}th"
        pct = round((pts / possible) * 100) if possible else 0
        lines.append(f"**{rank}** {user} — {pts}/{possible} ({pct}%)")
    e.description = "\n".join(lines)
    return e

# ═══════════════════════════════════════════════════════════════════════════════
#  GENERIC BET SELECT
# ═══════════════════════════════════════════════════════════════════════════════

class BetSelect(Select):
    def __init__(self, placeholder, key, game_id, uid, options):
        self.key = key
        self.game_id = game_id
        self.uid = uid
        super().__init__(placeholder=placeholder,
                         options=[discord.SelectOption(label=o, value=o) for o in options],
                         min_values=0, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid:
            await interaction.response.send_message("This is not your game.", ephemeral=True); return
        if self.values:
            active_games[self.game_id]["entries"][self.uid][self.key] = self.values[0]
        await interaction.response.defer()

# ═══════════════════════════════════════════════════════════════════════════════
#  STEP VIEWS  (max 4 selects + 1 button row per view)
# ═══════════════════════════════════════════════════════════════════════════════

class Step1LoverView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("Lover Bodysuit", "lover_bodysuit", game_id, uid, OUTFIT_OPTIONS["lover_bodysuit"]))
        self.add_item(BetSelect("The Man Jacket", "lover_jacket", game_id, uid, OUTFIT_OPTIONS["lover_jacket"]))
        self.add_item(BetSelect("Lover Guitar", "lover_guitar", game_id, uid, OUTFIT_OPTIONS["lover_guitar"]))

    @discord.ui.button(label="Next: Fearless / Red / Speak Now", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        entry = active_games[self.game_id]["entries"].get(self.uid, {})
        embed = discord.Embed(title="Fearless / Red / Speak Now", color=0xf1c40f,
                              description="Step 2 of 8 — pick your predictions. All optional.")
        embed.add_field(name="Step 1 saved",
                        value=f"Bodysuit: {entry.get('lover_bodysuit','—')}\nJacket: {entry.get('lover_jacket','—')}\nGuitar: {entry.get('lover_guitar','—')}", inline=False)
        await interaction.response.edit_message(embed=embed, view=Step2FearlessView(self.game_id, self.uid))


class Step2FearlessView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("Fearless Dress / Bodysuit", "fearless_dress", game_id, uid, OUTFIT_OPTIONS["fearless_dress"]))
        self.add_item(BetSelect("Red Shirt", "red_shirt", game_id, uid, OUTFIT_OPTIONS["red_shirt"]))
        self.add_item(BetSelect("Speak Now Dress", "speaknow_dress", game_id, uid, OUTFIT_OPTIONS["speaknow_dress"]))

    @discord.ui.button(label="Next: reputation / folklore", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="reputation / folklore", color=0x2c2f33,
                              description="Step 3 of 8 — pick your predictions. All optional.")
        await interaction.response.edit_message(embed=embed, view=Step3RepView(self.game_id, self.uid))


class Step3RepView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("rep Bodysuit", "rep_bodysuit", game_id, uid, OUTFIT_OPTIONS["rep_bodysuit"]))
        self.add_item(BetSelect("folklore Dress", "folklore_dress", game_id, uid, OUTFIT_OPTIONS["folklore_dress"]))

    @discord.ui.button(label="Next: 1989 Combo", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="1989 — Combo", color=0x3498db,
                              description="Step 4 of 8 — pick the top+skirt combo name, or skip and pick individual top/skirt on the next screen.")
        await interaction.response.edit_message(embed=embed, view=Step4_1989ComboView(self.game_id, self.uid))


class Step4_1989ComboView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("1989 Combo (A-Z, part 1)", "1989_combo", game_id, uid, OUTFIT_OPTIONS["1989_combo"]))
        self.add_item(BetSelect("1989 Combo (part 2)", "1989_combo", game_id, uid, OUTFIT_OPTIONS["1989_combo_b"]))

    @discord.ui.button(label="Next: 1989 Individual Top & Skirt", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        entry = active_games[self.game_id]["entries"].get(self.uid, {})
        embed = discord.Embed(title="1989 — Individual Top & Skirt", color=0x3498db,
                              description="Step 5 of 8 — pick individual top & skirt if you did not pick a combo.")
        embed.add_field(name="Combo saved", value=entry.get("1989_combo", "—"), inline=False)
        await interaction.response.edit_message(embed=embed, view=Step5_1989IndivView(self.game_id, self.uid))


class Step5_1989IndivView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("1989 Top", "1989_top", game_id, uid, OUTFIT_OPTIONS["1989_top"]))
        self.add_item(BetSelect("1989 Skirt", "1989_skirt", game_id, uid, OUTFIT_OPTIONS["1989_skirt"]))

    @discord.ui.button(label="Next: TTPD", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="The Tortured Poets Department", color=0x708090,
                              description="Step 6 of 8 — pick your TTPD predictions. All optional.")
        await interaction.response.edit_message(embed=embed, view=Step6TTPDView(self.game_id, self.uid))


class Step6TTPDView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("TTPD Dress", "ttpd_dress", game_id, uid, OUTFIT_OPTIONS["ttpd_dress"]))
        self.add_item(BetSelect("TTPD Set", "ttpd_set", game_id, uid, OUTFIT_OPTIONS["ttpd_set"]))
        self.add_item(BetSelect("TTPD Jacket / Cape", "ttpd_jacket", game_id, uid, OUTFIT_OPTIONS["ttpd_jacket"]))

    @discord.ui.button(label="Next: Midnights", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="Midnights", color=0x9b59b6,
                              description="Step 7 of 8 — pick your Midnights predictions. All optional.")
        await interaction.response.edit_message(embed=embed, view=Step7MidnightsView(self.game_id, self.uid))


class Step7MidnightsView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("Midnights Shirt Dress", "midnights_shirt", game_id, uid, OUTFIT_OPTIONS["midnights_shirt"]))
        self.add_item(BetSelect("Midnights Bodysuit", "midnights_body", game_id, uid, OUTFIT_OPTIONS["midnights_body"]))
        self.add_item(BetSelect("Karma Jacket", "karma_jacket", game_id, uid, OUTFIT_OPTIONS["karma_jacket"]))

    @discord.ui.button(label="Next: Surprise Songs & Final Picks", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="Surprise Songs & Final Picks", color=0xe67e22,
                              description="Step 8 of 8 — pick the surprise song dress and other predictions, then enter guitar & piano songs, then submit.")
        await interaction.response.edit_message(embed=embed, view=Step8FinalView(self.game_id, self.uid))


class SurpriseSongsModal(Modal, title="Surprise Song Predictions"):
    guitar_album = TextInput(label="Guitar: Album", placeholder="e.g. folklore", required=False, max_length=50)
    guitar_song  = TextInput(label="Guitar: Song Title", placeholder="e.g. seven", required=False, max_length=100)
    piano_album  = TextInput(label="Piano: Album", placeholder="e.g. Red (TV)", required=False, max_length=50)
    piano_song   = TextInput(label="Piano: Song Title", placeholder="e.g. All Too Well (10 Min)", required=False, max_length=100)

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
        await interaction.response.send_message("Songs saved! Hit Submit when ready.", ephemeral=True)

class NotesModal(Modal, title="Extra Notes"):
    notes = TextInput(label="Notes", placeholder="Any other predictions or comments...",
                      style=discord.TextStyle.paragraph, required=False, max_length=500)

    def __init__(self, game_id, uid):
        super().__init__()
        self.game_id = game_id; self.uid = uid

    async def on_submit(self, interaction: discord.Interaction):
        active_games[self.game_id]["entries"][self.uid]["notes"] = self.notes.value or "—"
        await interaction.response.send_message("Notes saved!", ephemeral=True)

class Step8FinalView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("Surprise Song Dress", "surprise_dress", game_id, uid, OUTFIT_OPTIONS["surprise_dress"]))
        self.add_item(BetSelect("Special Guest", "special_guest", game_id, uid, OUTFIT_OPTIONS["special_guest"]))
        self.add_item(BetSelect("Setlist Change", "setlist_change", game_id, uid, OUTFIT_OPTIONS["setlist_change"]))

    @discord.ui.button(label="Enter Guitar & Piano Songs", style=discord.ButtonStyle.secondary, row=4)
    async def songs_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        await interaction.response.send_modal(SurpriseSongsModal(self.game_id, self.uid))

    @discord.ui.button(label="Submit My Bets", style=discord.ButtonStyle.success, row=4)
    async def submit_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        entry = active_games[self.game_id]["entries"].get(self.uid, {})
        show  = active_games[self.game_id]["show"]
        embed = build_summary_embed(entry, show)
        await interaction.response.edit_message(content="Your bets are locked in.", embed=embed, view=None)


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC GAME VIEW
# ═══════════════════════════════════════════════════════════════════════════════

class MastermindGameView(View):
    def __init__(self, game_id):
        super().__init__(timeout=None)
        self.game_id = game_id

    @discord.ui.button(label="Play Mastermind", style=discord.ButtonStyle.success)
    async def play(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("This game no longer exists.", ephemeral=True); return
        if not game["open"]:
            await interaction.response.send_message("Submissions are closed.", ephemeral=True); return
        if interaction.user.id in game["entries"]:
            await interaction.response.send_message("You have already submitted your bets.", ephemeral=True); return
        uid = interaction.user.id
        ensure_entry(self.game_id, uid, str(interaction.user))
        embed = discord.Embed(title=f"Lover Era — {game['show']}",
                              description="Step 1 of 8 — pick your Lover era outfit predictions. All fields optional.",
                              color=0xff6b9d)
        await interaction.response.send_message(embed=embed, view=Step1LoverView(self.game_id, uid), ephemeral=True)

    @discord.ui.button(label="Entry Count", style=discord.ButtonStyle.secondary)
    async def count(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("Game not found.", ephemeral=True); return
        await interaction.response.send_message(f"{len(game['entries'])} player(s) have submitted bets.", ephemeral=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  ANSWER MODALS  (admin sets the real answers — 5 fields per modal max)
# ═══════════════════════════════════════════════════════════════════════════════

class AnswerModal1(Modal, title="Set Answers — Lover / Fearless / Red"):
    lover_bodysuit = TextInput(label="Lover Bodysuit", required=False, max_length=100)
    lover_jacket   = TextInput(label="The Man Jacket", required=False, max_length=100)
    lover_guitar   = TextInput(label="Lover Guitar", required=False, max_length=100)
    fearless_dress = TextInput(label="Fearless Dress / Bodysuit", required=False, max_length=100)
    red_shirt      = TextInput(label="Red Shirt", required=False, max_length=100)

    def __init__(self, game_id):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        a = active_games[self.game_id].setdefault("answers", {})
        if self.lover_bodysuit.value: a["lover_bodysuit"] = self.lover_bodysuit.value
        if self.lover_jacket.value:   a["lover_jacket"]   = self.lover_jacket.value
        if self.lover_guitar.value:   a["lover_guitar"]   = self.lover_guitar.value
        if self.fearless_dress.value: a["fearless_dress"] = self.fearless_dress.value
        if self.red_shirt.value:      a["red_shirt"]      = self.red_shirt.value
        await interaction.response.send_message("Part 1 saved. Click below to continue.", view=AnswerNextView(self.game_id, 2), ephemeral=True)

class AnswerModal2(Modal, title="Set Answers — Speak Now / rep / folklore"):
    speaknow_dress = TextInput(label="Speak Now Dress", required=False, max_length=100)
    rep_bodysuit   = TextInput(label="rep Bodysuit", required=False, max_length=100)
    folklore_dress = TextInput(label="folklore Dress", required=False, max_length=100)
    combo_1989     = TextInput(label="1989 Combo Name", required=False, max_length=100)
    top_1989       = TextInput(label="1989 Top", required=False, max_length=100)

    def __init__(self, game_id):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        a = active_games[self.game_id].setdefault("answers", {})
        if self.speaknow_dress.value: a["speaknow_dress"] = self.speaknow_dress.value
        if self.rep_bodysuit.value:   a["rep_bodysuit"]   = self.rep_bodysuit.value
        if self.folklore_dress.value: a["folklore_dress"] = self.folklore_dress.value
        if self.combo_1989.value:     a["1989_combo"]     = self.combo_1989.value
        if self.top_1989.value:       a["1989_top"]       = self.top_1989.value
        await interaction.response.send_message("Part 2 saved. Click below to continue.", view=AnswerNextView(self.game_id, 3), ephemeral=True)

class AnswerModal3(Modal, title="Set Answers — 1989 / TTPD"):
    skirt_1989    = TextInput(label="1989 Skirt", required=False, max_length=100)
    ttpd_dress    = TextInput(label="TTPD Dress", required=False, max_length=100)
    ttpd_set      = TextInput(label="TTPD Set", required=False, max_length=100)
    ttpd_jacket   = TextInput(label="TTPD Jacket / Cape", required=False, max_length=100)
    midnights_shirt = TextInput(label="Midnights Shirt Dress", required=False, max_length=100)

    def __init__(self, game_id):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        a = active_games[self.game_id].setdefault("answers", {})
        if self.skirt_1989.value:       a["1989_skirt"]       = self.skirt_1989.value
        if self.ttpd_dress.value:       a["ttpd_dress"]       = self.ttpd_dress.value
        if self.ttpd_set.value:         a["ttpd_set"]         = self.ttpd_set.value
        if self.ttpd_jacket.value:      a["ttpd_jacket"]      = self.ttpd_jacket.value
        if self.midnights_shirt.value:  a["midnights_shirt"]  = self.midnights_shirt.value
        await interaction.response.send_message("Part 3 saved. Click below to continue.", view=AnswerNextView(self.game_id, 4), ephemeral=True)

class AnswerModal4(Modal, title="Set Answers — Midnights / Surprise Songs"):
    midnights_body = TextInput(label="Midnights Bodysuit", required=False, max_length=100)
    karma_jacket   = TextInput(label="Karma Jacket", required=False, max_length=100)
    surprise_dress = TextInput(label="Surprise Song Dress", required=False, max_length=100)
    guitar_album   = TextInput(label="Guitar Surprise: Album", required=False, max_length=100)
    guitar_song    = TextInput(label="Guitar Surprise: Song", required=False, max_length=100)

    def __init__(self, game_id):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        a = active_games[self.game_id].setdefault("answers", {})
        if self.midnights_body.value: a["midnights_body"] = self.midnights_body.value
        if self.karma_jacket.value:   a["karma_jacket"]   = self.karma_jacket.value
        if self.surprise_dress.value: a["surprise_dress"] = self.surprise_dress.value
        if self.guitar_album.value:   a["guitar_album"]   = self.guitar_album.value
        if self.guitar_song.value:    a["guitar_song"]    = self.guitar_song.value
        await interaction.response.send_message("Part 4 saved. Click below to continue.", view=AnswerNextView(self.game_id, 5), ephemeral=True)

class AnswerModal5(Modal, title="Set Answers — Piano / Other"):
    piano_album     = TextInput(label="Piano Surprise: Album", required=False, max_length=100)
    piano_song      = TextInput(label="Piano Surprise: Song", required=False, max_length=100)
    special_guest   = TextInput(label="Special Guest", required=False, max_length=100)
    setlist_change  = TextInput(label="Setlist Change", required=False, max_length=100)
    notes           = TextInput(label="Any other notes", required=False, max_length=200)

    def __init__(self, game_id):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        a = active_games[self.game_id].setdefault("answers", {})
        if self.piano_album.value:    a["piano_album"]    = self.piano_album.value
        if self.piano_song.value:     a["piano_song"]     = self.piano_song.value
        if self.special_guest.value:  a["special_guest"]  = self.special_guest.value
        if self.setlist_change.value: a["setlist_change"] = self.setlist_change.value

        # Auto-close game and post results panel
        active_games[self.game_id]["open"] = False
        game = active_games[self.game_id]
        show = game["show"]

        lb_embed = build_leaderboard_embed(game)
        lb_embed.set_footer(text="Click 'View Full Results' to see each player's breakdown.")

        # Post to the channel the game is in, or reply here
        view = ResultsPanelView(self.game_id)
        await interaction.response.send_message(
            content=f"Answers saved! Game closed. Leaderboard for **{show}**:",
            embed=lb_embed,
            view=view,
            ephemeral=False
        )

ANSWER_MODALS = [None, AnswerModal1, AnswerModal2, AnswerModal3, AnswerModal4, AnswerModal5]

class AnswerNextView(View):
    def __init__(self, game_id, next_part):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.next_part = next_part

    @discord.ui.button(label="Continue to Next Part", style=discord.ButtonStyle.primary)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        modal_cls = ANSWER_MODALS[self.next_part]
        await interaction.response.send_modal(modal_cls(self.game_id))


# ═══════════════════════════════════════════════════════════════════════════════
#  RESULTS PANEL VIEW
# ═══════════════════════════════════════════════════════════════════════════════

class ResultsPanelView(View):
    def __init__(self, game_id):
        super().__init__(timeout=None)
        self.game_id = game_id

    @discord.ui.button(label="View Full Results", style=discord.ButtonStyle.primary)
    async def full_results(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("Game not found.", ephemeral=True); return
        answers = game.get("answers", {})
        if not answers:
            await interaction.response.send_message("No answers have been set yet.", ephemeral=True); return

        embeds = []
        for uid, entry in list(game["entries"].items())[:10]:
            e, pts, possible = build_score_embed(entry, answers, game["show"])
            embeds.append(e)

        if not embeds:
            await interaction.response.send_message("No entries to show.", ephemeral=True); return
        await interaction.response.send_message(embeds=embeds, ephemeral=True)

    @discord.ui.button(label="Refresh Leaderboard", style=discord.ButtonStyle.secondary)
    async def refresh_lb(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("Game not found.", ephemeral=True); return
        embed = build_leaderboard_embed(game)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="View All Submissions", style=discord.ButtonStyle.secondary)
    async def all_submissions(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game or not game["entries"]:
            await interaction.response.send_message("No entries yet.", ephemeral=True); return
        embeds = [build_summary_embed(e, game["show"]) for e in list(game["entries"].values())[:10]]
        await interaction.response.send_message(embeds=embeds, ephemeral=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN — CREATE GAME
# ═══════════════════════════════════════════════════════════════════════════════

class CreateGameModal(Modal, title="Create Mastermind Game"):
    show_name   = TextInput(label="Show Name / Date", placeholder="e.g. Sydney Night 1 — Feb 23, 2024", max_length=100)
    description = TextInput(label="Description", placeholder="Place your bets before the show!", style=discord.TextStyle.paragraph, required=False)
    thumbnail   = TextInput(label="Thumbnail Image URL (optional)", placeholder="https://example.com/eras.png", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        game_id = f"{interaction.guild_id}_{int(datetime.now(timezone.utc).timestamp())}"
        active_games[game_id] = {"show": self.show_name.value, "open": True, "entries": {}, "answers": {}}
        desc = self.description.value or "Think you know what Taylor will wear and play? Place your bets before the show starts!"
        embed = discord.Embed(title=f"Eras Tour Mastermind — {self.show_name.value}", description=desc, color=0xff6b9d)
        embed.add_field(name="Lover", value="Bodysuit / The Man Jacket / Guitar", inline=True)
        embed.add_field(name="Fearless / Red / Speak Now", value="Fearless Dress / Red Shirt / Speak Now Dress", inline=True)
        embed.add_field(name="rep / folklore", value="rep Bodysuit / folklore Dress", inline=False)
        embed.add_field(name="1989", value="Combo OR Top + Skirt", inline=True)
        embed.add_field(name="TTPD", value="Dress / Set / Jacket/Cape", inline=True)
        embed.add_field(name="Midnights", value="Shirt Dress / Bodysuit / Karma Jacket", inline=False)
        embed.add_field(name="Surprise Songs", value="Dress / Guitar (Album + Song) / Piano (Album + Song)", inline=False)
        embed.add_field(name="Other", value="Special Guest / Setlist Change", inline=False)
        embed.set_footer(text="Click Play Mastermind to place your bets.")
        if self.thumbnail.value:
            embed.set_thumbnail(url=self.thumbnail.value)
        await interaction.response.send_message(embed=embed, view=MastermindGameView(game_id))


# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN — GAME PICKER SELECTS
# ═══════════════════════════════════════════════════════════════════════════════

class GamePickerSelect(Select):
    def __init__(self, games, action):
        self.action = action
        super().__init__(placeholder="Select a game...",
                         options=[discord.SelectOption(label=g["show"][:100], value=gid) for gid, g in games])

    async def callback(self, interaction: discord.Interaction):
        gid = self.values[0]
        game = active_games.get(gid)
        if not game:
            await interaction.response.send_message("Game not found.", ephemeral=True); return

        if self.action == "close":
            game["open"] = False
            await interaction.response.send_message(f"**{game['show']}** is now closed.", ephemeral=True)
        elif self.action == "entries":
            if not game["entries"]:
                await interaction.response.send_message("No entries yet.", ephemeral=True); return
            embeds = [build_summary_embed(e, game["show"]) for e in list(game["entries"].values())[:10]]
            await interaction.response.send_message(embeds=embeds, ephemeral=True)
        elif self.action == "answers":
            await interaction.response.send_modal(AnswerModal1(gid))

class GamePickerView(View):
    def __init__(self, games, action):
        super().__init__(timeout=60)
        self.add_item(GamePickerSelect(games, action))


# ═══════════════════════════════════════════════════════════════════════════════
#  BULLETIN SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

class BulletinModal(Modal, title="Create Bulletin"):
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
        await interaction.response.send_message("Preview:", embed=embed, view=BulletinConfirmView(embed), ephemeral=True)

class ColorSelect(Select):
    def __init__(self):
        super().__init__(placeholder="Pick a color...",
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

    @discord.ui.button(label="Post", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        ok = await post_to_webhook(self.embed)
        await interaction.followup.send("Posted!" if ok else "Failed to post.", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Cancelled.", ephemeral=True)

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary)
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
    await interaction.response.send_message("Bulletin Builder — pick a color:", view=ColorPickerView(), ephemeral=True)

mastermind_group = app_commands.Group(name="mastermind", description="Eras Tour Mastermind guessing game")

@mastermind_group.command(name="create", description="[Admin] Create a new Mastermind game for a show")
async def mastermind_create(interaction: discord.Interaction):
    await interaction.response.send_modal(CreateGameModal())

@mastermind_group.command(name="close", description="[Admin] Close submissions for a game")
async def mastermind_close(interaction: discord.Interaction):
    games = [(gid, g) for gid, g in active_games.items() if g.get("open")]
    if not games:
        await interaction.response.send_message("No open games.", ephemeral=True); return
    await interaction.response.send_message("Select a game to close:", view=GamePickerView(games, "close"), ephemeral=True)

@mastermind_group.command(name="entries", description="[Admin] View all entries for a game")
async def mastermind_entries(interaction: discord.Interaction):
    if not active_games:
        await interaction.response.send_message("No games found.", ephemeral=True); return
    await interaction.response.send_message("Select a game:", view=GamePickerView(list(active_games.items()), "entries"), ephemeral=True)

@mastermind_group.command(name="list", description="List all active games and entry counts")
async def mastermind_list(interaction: discord.Interaction):
    if not active_games:
        await interaction.response.send_message("No active games.", ephemeral=True); return
    lines = [f"**{g['show']}** — {'Open' if g['open'] else 'Closed'} — {len(g['entries'])} entries"
             for g in active_games.values()]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

answer_group = app_commands.Group(name="answer", description="Set answers and score results", parent=mastermind_group)

@answer_group.command(name="create", description="[Admin] Set the real answers for a show and publish results")
async def answer_create(interaction: discord.Interaction):
    if not active_games:
        await interaction.response.send_message("No games found.", ephemeral=True); return
    await interaction.response.send_message("Select a game to set answers for:", view=GamePickerView(list(active_games.items()), "answers"), ephemeral=True)

mastermind_group.add_command(answer_group)
tree.add_command(mastermind_group)

@client.event
async def on_ready():
    await tree.sync()
    print(f"Logged in as {client.user} — slash commands synced.")

client.run(BOT_TOKEN)
