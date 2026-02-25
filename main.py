import discord
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button, Select
import aiohttp
import json
import os
import asyncio
import yt_dlp
from collections import deque
from datetime import datetime, timezone

# ─── CONFIG ───────────────────────────────────────────────────────────────────
WEBHOOK_URL  = "https://discord.com/api/webhooks/1475369638001901761/juynubLrFgKHt9cG5E4tGCfj5DZdO5JDPdhu8pREGVEBEVxFCRZxYvwqisLTiyqfWxoa"
BOT_TOKEN    = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_ROLE   = 1475027064817188906
# ──────────────────────────────────────────────────────────────────────────────

active_games: dict = {}

# ═══════════════════════════════════════════════════════════════════════════════
#  MUSIC SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

music_queues: dict = {}   # guild_id -> deque of track dicts
now_playing:  dict = {}   # guild_id -> current track dict

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": False,
    "quiet": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cookiefile": None,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

def get_queue(guild_id: int) -> deque:
    if guild_id not in music_queues:
        music_queues[guild_id] = deque()
    return music_queues[guild_id]

async def fetch_track(query: str) -> dict | None:
    """Search or resolve a URL and return track info dict."""
    loop = asyncio.get_event_loop()
    def _extract():
        with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return {
                "title":     info.get("title", "Unknown"),
                "url":       info["url"],
                "webpage":   info.get("webpage_url", ""),
                "duration":  info.get("duration", 0),
                "thumbnail": info.get("thumbnail", ""),
                "requester": None,
            }
    try:
        return await loop.run_in_executor(None, _extract)
    except Exception as e:
        print(f"yt_dlp error: {e}")
        return None

def fmt_duration(seconds: int) -> str:
    if not seconds:
        return "Unknown"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"

async def update_bot_status(track: dict | None):
    if track:
        await client.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name=track["title"]
            )
        )
    else:
        await client.change_presence(activity=discord.Game(name="Nothing playing"))

async def play_next(guild: discord.Guild, voice_client: discord.VoiceClient):
    queue = get_queue(guild.id)
    if not queue:
        now_playing[guild.id] = None
        await update_bot_status(None)
        # Update channel name back
        if voice_client and voice_client.channel:
            try:
                await voice_client.channel.edit(name="music")
            except Exception:
                pass
        return

    track = queue.popleft()
    now_playing[guild.id] = track

    await update_bot_status(track)

    # Update voice channel name to show current song (truncated to 100 chars)
    if voice_client and voice_client.channel:
        try:
            short = track["title"][:90]
            await voice_client.channel.edit(name=f"♪ {short}")
        except Exception:
            pass

    def after_play(error):
        if error:
            print(f"Playback error: {error}")
        asyncio.run_coroutine_threadsafe(
            play_next(guild, voice_client), client.loop
        )

    source = discord.FFmpegPCMAudio(track["url"], **FFMPEG_OPTIONS)
    source = discord.PCMVolumeTransformer(source, volume=0.5)
    voice_client.play(source, after=after_play)

def build_now_playing_embed(guild_id: int) -> discord.Embed:
    track = now_playing.get(guild_id)
    queue = get_queue(guild_id)
    if not track:
        e = discord.Embed(title="Nothing playing", color=0x2c2f33)
        e.description = f"{len(queue)} track(s) in queue."
        return e
    e = discord.Embed(title="Now Playing", description=f"**[{track['title']}]({track['webpage']})**", color=0x1db954)
    e.add_field(name="Duration", value=fmt_duration(track["duration"]), inline=True)
    e.add_field(name="Requested by", value=track.get("requester") or "Unknown", inline=True)
    e.add_field(name="Queue", value=f"{len(queue)} track(s) up next", inline=True)
    if track["thumbnail"]:
        e.set_thumbnail(url=track["thumbnail"])
    if queue:
        next_tracks = list(queue)[:5]
        lines = [f"{i+1}. {t['title']} ({fmt_duration(t['duration'])})" for i, t in enumerate(next_tracks)]
        if len(queue) > 5:
            lines.append(f"... and {len(queue) - 5} more")
        e.add_field(name="Up Next", value="\n".join(lines), inline=False)
    return e

# ─── MUSIC PANEL VIEW ─────────────────────────────────────────────────────────

class MusicPanelView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    def _get_vc(self) -> discord.VoiceClient | None:
        guild = client.get_guild(self.guild_id)
        return guild.voice_client if guild else None

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary, row=0)
    async def pause_btn(self, interaction: discord.Interaction, button: Button):
        vc = self._get_vc()
        if vc and vc.is_playing():
            vc.pause()
            await interaction.response.edit_message(embed=build_now_playing_embed(self.guild_id), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Resume", style=discord.ButtonStyle.success, row=0)
    async def resume_btn(self, interaction: discord.Interaction, button: Button):
        vc = self._get_vc()
        if vc and vc.is_paused():
            vc.resume()
            await interaction.response.edit_message(embed=build_now_playing_embed(self.guild_id), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.primary, row=0)
    async def skip_btn(self, interaction: discord.Interaction, button: Button):
        vc = self._get_vc()
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.edit_message(embed=build_now_playing_embed(self.guild_id), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Stop & Clear", style=discord.ButtonStyle.danger, row=0)
    async def stop_btn(self, interaction: discord.Interaction, button: Button):
        vc = self._get_vc()
        get_queue(self.guild_id).clear()
        now_playing[self.guild_id] = None
        if vc:
            vc.stop()
            await vc.disconnect()
        await update_bot_status(None)
        await interaction.response.edit_message(embed=build_now_playing_embed(self.guild_id), view=self)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, row=0)
    async def refresh_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(embed=build_now_playing_embed(self.guild_id), view=self)

    @discord.ui.button(label="Volume -", style=discord.ButtonStyle.secondary, row=1)
    async def vol_down(self, interaction: discord.Interaction, button: Button):
        vc = self._get_vc()
        if vc and vc.source:
            vc.source.volume = max(0.0, vc.source.volume - 0.1)
            await interaction.response.send_message(f"Volume: {round(vc.source.volume * 100)}%", ephemeral=True)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Volume +", style=discord.ButtonStyle.secondary, row=1)
    async def vol_up(self, interaction: discord.Interaction, button: Button):
        vc = self._get_vc()
        if vc and vc.source:
            vc.source.volume = min(2.0, vc.source.volume + 0.1)
            await interaction.response.send_message(f"Volume: {round(vc.source.volume * 100)}%", ephemeral=True)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="View Queue", style=discord.ButtonStyle.secondary, row=1)
    async def queue_btn(self, interaction: discord.Interaction, button: Button):
        queue = list(get_queue(self.guild_id))
        if not queue:
            await interaction.response.send_message("Queue is empty.", ephemeral=True); return
        lines = [f"{i+1}. **{t['title']}** ({fmt_duration(t['duration'])}) — {t.get('requester','?')}"
                 for i, t in enumerate(queue[:20])]
        if len(queue) > 20:
            lines.append(f"... and {len(queue) - 20} more")
        e = discord.Embed(title="Queue", description="\n".join(lines), color=0x1db954)
        await interaction.response.send_message(embed=e, ephemeral=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  EXISTING BOT CODE (unchanged below)
# ═══════════════════════════════════════════════════════════════════════════════

COLORS = {
    "Blue": 0x3498db, "Green": 0x2ecc71, "Red": 0xe74c3c,
    "Yellow": 0xf1c40f, "Purple": 0x9b59b6, "Orange": 0xe67e22,
    "White": 0xffffff, "Black": 0x2c2f33, "Pink": 0xff6b9d, "Cyan": 0x00d2d3,
}

SCORE_FIELDS = [
    ("lover_bodysuit",  "Lover Bodysuit"),
    ("lover_jacket",    "Lover Jacket"),
    ("lover_guitar",    "Lover Guitar"),
    ("fearless_dress",  "Fearless Dress"),
    ("red_shirt",       "Red Shirt"),
    ("speaknow_dress",  "Speak Now Dress"),
    ("rep_bodysuit",    "rep Bodysuit"),
    ("folklore_dress",  "folklore Dress"),
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
    "lover_bodysuit":  ["Pink & Blue Bodysuit", "Gold & Blue Bodysuit", "Purple Bodysuit", "Pink Bodysuit", "Tangerine (Orange) Bodysuit"],
    "lover_jacket":    ["Silver The Man Jacket", "Black The Man Jacket", "Purple The Man Jacket", "Pink The Man Jacket", "Tangerine The Man Jacket"],
    "lover_guitar":    ["Pink Guitar", "Blue Guitar", "Lavender Guitar"],
    "fearless_dress":  ["Short Gold", "Long Gold", "Long Silver", "Black & Silver"],
    "red_shirt":       ["A Lot Going On", "Ew", "Like Ever", "Taylor's Version", "About Me", "Trouble"],
    "speaknow_dress":  ["Champagne Dress", "Pink Dress", "Tissue Paper Dress", "Silver Dress", "Purple Dress", "Blue Dress", "Swirls Dress"],
    "rep_bodysuit":    ["Black & Red"],
    "folklore_dress":  ["Purple Dress", "Cream Dress", "Pink Dress", "Green Dress", "Blue Dress", "Yellow Dress", "Berry Dress"],
    "1989_top":        ["Orange Top", "Green Top", "Blue Top", "Yellow Top", "Pink Top", "Purple Top"],
    "1989_skirt":      ["Orange Skirt", "Green Skirt", "Blue Skirt", "Yellow Skirt", "Pink Skirt", "Purple Skirt"],
    "ttpd_dress":      ["White Dress"],
    "ttpd_set":        ["Black", "White", "Graphite"],
    "ttpd_jacket":     ["Gold", "White", "Graphite", "Silver"],
    "surprise_dress":  ["Bright Pink", "Ocean Blue", "Sunset (Orange)"],
    "midnights_shirt": ["Dark Purple", "Bright Blue", "Silver", "Pink", "Light Purple", "Iridescent"],
    "midnights_body":  ["Dark Blue", "Scallops", "Cutouts", "Chevron"],
    "karma_jacket":    ["Multicolor", "Magenta", "Blue", "Pink", "No Jacket"],
    "special_guest":   ["Sabrina Carpenter", "Gracie Abrams", "Muna", "Phoebe Bridgers", "Marcus Mumford", "Haim", "Ed Sheeran", "Ice Spice", "Paramore", "No Special Guest"],
    "setlist_change":  ["Song Added", "Song Removed", "Song Swapped", "No Changes"],
}

def is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    return any(r.id == ADMIN_ROLE for r in interaction.user.roles)

async def deny(interaction: discord.Interaction):
    await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

def ensure_entry(game_id, uid, user_str):
    if uid not in active_games[game_id]["entries"]:
        active_games[game_id]["entries"][uid] = {"user": user_str}

def score_entry(entry, answers):
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
    e.add_field(name="Lover", value=f"Bodysuit: {entry.get('lover_bodysuit','—')}\nJacket: {entry.get('lover_jacket','—')}\nGuitar: {entry.get('lover_guitar','—')}", inline=False)
    e.add_field(name="Fearless / Red / Speak Now", value=f"Fearless: {entry.get('fearless_dress','—')}\nRed Shirt: {entry.get('red_shirt','—')}\nSpeak Now: {entry.get('speaknow_dress','—')}", inline=False)
    e.add_field(name="rep / folklore", value=f"rep Bodysuit: {entry.get('rep_bodysuit','—')}\nfolklore Dress: {entry.get('folklore_dress','—')}", inline=False)
    e.add_field(name="1989", value=f"Top: {entry.get('1989_top','—')}\nSkirt: {entry.get('1989_skirt','—')}", inline=False)
    e.add_field(name="TTPD", value=f"Dress: {entry.get('ttpd_dress','—')}\nSet: {entry.get('ttpd_set','—')}\nJacket/Cape: {entry.get('ttpd_jacket','—')}", inline=False)
    e.add_field(name="Midnights", value=f"Shirt Dress: {entry.get('midnights_shirt','—')}\nBodysuit: {entry.get('midnights_body','—')}\nKarma Jacket: {entry.get('karma_jacket','—')}", inline=False)
    e.add_field(name="Surprise Songs", value=f"Dress: {entry.get('surprise_dress','—')}\nGuitar: {entry.get('guitar_album','—')} — {entry.get('guitar_song','—')}\nPiano: {entry.get('piano_album','—')} — {entry.get('piano_song','—')}", inline=False)
    e.add_field(name="Other", value=f"Guest: {entry.get('special_guest','—')}\nSetlist: {entry.get('setlist_change','—')}\nNotes: {entry.get('notes','—')}", inline=False)
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
    correct_lines, wrong_lines = [], []
    for key, label in SCORE_FIELDS:
        if key not in results:
            continue
        if results[key]["correct"]:
            correct_lines.append(f"{label}: {results[key]['guess']}")
        else:
            wrong_lines.append(f"{label}: guessed **{results[key]['guess']}**, answer **{results[key]['answer']}**")
    if correct_lines:
        e.add_field(name=f"Correct ({len(correct_lines)})", value="\n".join(correct_lines), inline=False)
    if wrong_lines:
        e.add_field(name=f"Wrong ({len(wrong_lines)})", value="\n".join(wrong_lines), inline=False)
    return e, points, possible

def build_leaderboard_embed(game):
    answers = game.get("answers", {})
    scores = []
    for uid, entry in game["entries"].items():
        pts, possible, _ = score_entry(entry, answers)
        scores.append((entry.get("user", str(uid)), pts, possible))
    scores.sort(key=lambda x: x[1], reverse=True)
    e = discord.Embed(title=f"Leaderboard — {game['show']}", color=0x5865f2)
    if not scores:
        e.description = "No entries yet."
        return e
    medals = ["1st", "2nd", "3rd"]
    lines = []
    for i, (user, pts, possible) in enumerate(scores):
        rank = medals[i] if i < 3 else f"{i+1}th"
        pct = round((pts / possible) * 100) if possible else 0
        lines.append(f"**{rank}** {user} — {pts}/{possible} ({pct}%)")
    e.description = "\n".join(lines)
    return e

class BetSelect(Select):
    def __init__(self, placeholder, key, game_id, uid, options):
        self.key = key; self.game_id = game_id; self.uid = uid
        super().__init__(placeholder=placeholder,
                         options=[discord.SelectOption(label=o, value=o) for o in options],
                         min_values=0, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.uid:
            await interaction.response.send_message("This is not your game.", ephemeral=True); return
        if self.values:
            active_games[self.game_id]["entries"][self.uid][self.key] = self.values[0]
        await interaction.response.defer()

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
        embed = discord.Embed(title="Fearless / Red / Speak Now", color=0xf1c40f, description="Step 2 of 7 — All optional.")
        embed.add_field(name="Step 1 saved", value=f"Bodysuit: {entry.get('lover_bodysuit','—')}\nJacket: {entry.get('lover_jacket','—')}\nGuitar: {entry.get('lover_guitar','—')}", inline=False)
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
        embed = discord.Embed(title="reputation / folklore", color=0x2c2f33, description="Step 3 of 7 — All optional.")
        await interaction.response.edit_message(embed=embed, view=Step3RepView(self.game_id, self.uid))

class Step3RepView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("rep Bodysuit", "rep_bodysuit", game_id, uid, OUTFIT_OPTIONS["rep_bodysuit"]))
        self.add_item(BetSelect("folklore Dress", "folklore_dress", game_id, uid, OUTFIT_OPTIONS["folklore_dress"]))

    @discord.ui.button(label="Next: 1989", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="1989", color=0x3498db, description="Step 4 of 7 — All optional.")
        await interaction.response.edit_message(embed=embed, view=Step4_1989View(self.game_id, self.uid))

class Step4_1989View(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("1989 Top", "1989_top", game_id, uid, OUTFIT_OPTIONS["1989_top"]))
        self.add_item(BetSelect("1989 Skirt", "1989_skirt", game_id, uid, OUTFIT_OPTIONS["1989_skirt"]))

    @discord.ui.button(label="Next: TTPD", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="The Tortured Poets Department", color=0x708090, description="Step 5 of 7 — All optional.")
        await interaction.response.edit_message(embed=embed, view=Step5TTPDView(self.game_id, self.uid))

class Step5TTPDView(View):
    def __init__(self, game_id, uid):
        super().__init__(timeout=300)
        self.game_id = game_id; self.uid = uid
        self.add_item(BetSelect("TTPD Dress", "ttpd_dress", game_id, uid, OUTFIT_OPTIONS["ttpd_dress"]))
        self.add_item(BetSelect("TTPD Set", "ttpd_set", game_id, uid, OUTFIT_OPTIONS["ttpd_set"]))
        self.add_item(BetSelect("TTPD Jacket / Cape", "ttpd_jacket", game_id, uid, OUTFIT_OPTIONS["ttpd_jacket"]))

    @discord.ui.button(label="Next: Midnights", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.uid: return
        embed = discord.Embed(title="Midnights", color=0x9b59b6, description="Step 6 of 7 — All optional.")
        await interaction.response.edit_message(embed=embed, view=Step6MidnightsView(self.game_id, self.uid))

class Step6MidnightsView(View):
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
                              description="Step 7 of 7 — Pick the surprise song dress and other predictions, then enter guitar & piano songs, then submit.")
        await interaction.response.edit_message(embed=embed, view=Step7FinalView(self.game_id, self.uid))

class SurpriseSongsModal(Modal, title="Surprise Song Predictions"):
    guitar_album = TextInput(label="Guitar: Album", placeholder="e.g. folklore", required=False, max_length=50)
    guitar_song  = TextInput(label="Guitar: Song Title", placeholder="e.g. Seven", required=False, max_length=100)
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

class Step7FinalView(View):
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
        embed = build_summary_embed(entry, active_games[self.game_id]["show"])
        await interaction.response.edit_message(content="Your bets are locked in.", embed=embed, view=None)

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
                              description="Step 1 of 7 — pick your Lover era outfit predictions. All fields optional.",
                              color=0xff6b9d)
        await interaction.response.send_message(embed=embed, view=Step1LoverView(self.game_id, uid), ephemeral=True)

    @discord.ui.button(label="Entry Count", style=discord.ButtonStyle.secondary)
    async def count(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game:
            await interaction.response.send_message("Game not found.", ephemeral=True); return
        await interaction.response.send_message(f"{len(game['entries'])} player(s) have submitted bets.", ephemeral=True)

class AnswerSelect(Select):
    def __init__(self, placeholder, key, game_id, options, extra_option=True):
        self.key = key; self.game_id = game_id
        opts = list(options)
        if extra_option and "N/A (Not Worn)" not in opts:
            opts = opts + ["N/A (Not Worn)"]
        super().__init__(placeholder=placeholder,
                         options=[discord.SelectOption(label=o, value=o) for o in opts],
                         min_values=0, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if self.values:
            active_games[self.game_id]["answers"][self.key] = self.values[0]
        await interaction.response.defer()

class AnswerStep1LoverView(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.add_item(AnswerSelect("Lover Bodysuit", "lover_bodysuit", game_id, OUTFIT_OPTIONS["lover_bodysuit"]))
        self.add_item(AnswerSelect("The Man Jacket", "lover_jacket", game_id, OUTFIT_OPTIONS["lover_jacket"]))
        self.add_item(AnswerSelect("Lover Guitar", "lover_guitar", game_id, OUTFIT_OPTIONS["lover_guitar"]))

    @discord.ui.button(label="Next: Fearless / Red / Speak Now", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="Set Answers — Fearless / Red / Speak Now", color=0xf1c40f, description="Select the correct answer for each category.")
        await interaction.response.edit_message(embed=embed, view=AnswerStep2View(self.game_id))

class AnswerStep2View(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.add_item(AnswerSelect("Fearless Dress / Bodysuit", "fearless_dress", game_id, OUTFIT_OPTIONS["fearless_dress"]))
        self.add_item(AnswerSelect("Red Shirt", "red_shirt", game_id, OUTFIT_OPTIONS["red_shirt"]))
        self.add_item(AnswerSelect("Speak Now Dress", "speaknow_dress", game_id, OUTFIT_OPTIONS["speaknow_dress"]))

    @discord.ui.button(label="Next: reputation / folklore", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="Set Answers — reputation / folklore", color=0x2c2f33, description="Select the correct answer for each category.")
        await interaction.response.edit_message(embed=embed, view=AnswerStep3View(self.game_id))

class AnswerStep3View(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.add_item(AnswerSelect("rep Bodysuit", "rep_bodysuit", game_id, OUTFIT_OPTIONS["rep_bodysuit"]))
        self.add_item(AnswerSelect("folklore Dress", "folklore_dress", game_id, OUTFIT_OPTIONS["folklore_dress"]))

    @discord.ui.button(label="Next: 1989", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="Set Answers — 1989", color=0x3498db, description="Select the correct answer for each category.")
        await interaction.response.edit_message(embed=embed, view=AnswerStep4View(self.game_id))

class AnswerStep4View(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.add_item(AnswerSelect("1989 Top", "1989_top", game_id, OUTFIT_OPTIONS["1989_top"]))
        self.add_item(AnswerSelect("1989 Skirt", "1989_skirt", game_id, OUTFIT_OPTIONS["1989_skirt"]))

    @discord.ui.button(label="Next: TTPD", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="Set Answers — TTPD", color=0x708090, description="Select the correct answer for each category.")
        await interaction.response.edit_message(embed=embed, view=AnswerStep5View(self.game_id))

class AnswerStep5View(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.add_item(AnswerSelect("TTPD Dress", "ttpd_dress", game_id, OUTFIT_OPTIONS["ttpd_dress"]))
        self.add_item(AnswerSelect("TTPD Set", "ttpd_set", game_id, OUTFIT_OPTIONS["ttpd_set"]))
        self.add_item(AnswerSelect("TTPD Jacket / Cape", "ttpd_jacket", game_id, OUTFIT_OPTIONS["ttpd_jacket"]))

    @discord.ui.button(label="Next: Midnights", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="Set Answers — Midnights", color=0x9b59b6, description="Select the correct answer for each category.")
        await interaction.response.edit_message(embed=embed, view=AnswerStep6View(self.game_id))

class AnswerStep6View(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.add_item(AnswerSelect("Midnights Shirt Dress", "midnights_shirt", game_id, OUTFIT_OPTIONS["midnights_shirt"]))
        self.add_item(AnswerSelect("Midnights Bodysuit", "midnights_body", game_id, OUTFIT_OPTIONS["midnights_body"]))
        self.add_item(AnswerSelect("Karma Jacket", "karma_jacket", game_id, OUTFIT_OPTIONS["karma_jacket"]))

    @discord.ui.button(label="Next: Surprise Songs & Other", style=discord.ButtonStyle.primary, row=4)
    async def next_btn(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(title="Set Answers — Surprise Songs & Other", color=0xe67e22,
                              description="Select the correct answers, then enter guitar & piano songs, then click Publish Results.")
        await interaction.response.edit_message(embed=embed, view=AnswerStep7View(self.game_id))

class AnswerSongsModal(Modal, title="Set Surprise Song Answers"):
    guitar_album = TextInput(label="Guitar Surprise: Album", placeholder="e.g. folklore", required=False, max_length=50)
    guitar_song  = TextInput(label="Guitar Surprise: Song", placeholder="e.g. Seven", required=False, max_length=100)
    piano_album  = TextInput(label="Piano Surprise: Album", placeholder="e.g. Red (TV)", required=False, max_length=50)
    piano_song   = TextInput(label="Piano Surprise: Song", placeholder="e.g. All Too Well (10 Min)", required=False, max_length=100)

    def __init__(self, game_id):
        super().__init__()
        self.game_id = game_id

    async def on_submit(self, interaction: discord.Interaction):
        a = active_games[self.game_id]["answers"]
        if self.guitar_album.value: a["guitar_album"] = self.guitar_album.value
        if self.guitar_song.value:  a["guitar_song"]  = self.guitar_song.value
        if self.piano_album.value:  a["piano_album"]  = self.piano_album.value
        if self.piano_song.value:   a["piano_song"]   = self.piano_song.value
        await interaction.response.send_message("Surprise songs saved! Click Publish Results when ready.", ephemeral=True)

class AnswerStep7View(View):
    def __init__(self, game_id):
        super().__init__(timeout=300)
        self.game_id = game_id
        self.add_item(AnswerSelect("Surprise Song Dress", "surprise_dress", game_id, OUTFIT_OPTIONS["surprise_dress"]))
        self.add_item(AnswerSelect("Special Guest", "special_guest", game_id, OUTFIT_OPTIONS["special_guest"]))
        self.add_item(AnswerSelect("Setlist Change", "setlist_change", game_id, OUTFIT_OPTIONS["setlist_change"]))

    @discord.ui.button(label="Enter Guitar & Piano Songs", style=discord.ButtonStyle.secondary, row=4)
    async def songs_btn(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(AnswerSongsModal(self.game_id))

    @discord.ui.button(label="Publish Results", style=discord.ButtonStyle.success, row=4)
    async def publish_btn(self, interaction: discord.Interaction, button: Button):
        game = active_games[self.game_id]
        game["open"] = False
        lb_embed = build_leaderboard_embed(game)
        lb_embed.set_footer(text="Use the buttons below to view full results and submissions.")
        await interaction.response.edit_message(
            content=f"Answers saved. Results for **{game['show']}**:",
            embed=lb_embed,
            view=ResultsPanelView(self.game_id)
        )

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
        await interaction.response.send_message(embed=build_leaderboard_embed(game), ephemeral=True)

    @discord.ui.button(label="View All Submissions", style=discord.ButtonStyle.secondary)
    async def all_submissions(self, interaction: discord.Interaction, button: Button):
        game = active_games.get(self.game_id)
        if not game or not game["entries"]:
            await interaction.response.send_message("No entries yet.", ephemeral=True); return
        embeds = [build_summary_embed(e, game["show"]) for e in list(game["entries"].values())[:10]]
        await interaction.response.send_message(embeds=embeds, ephemeral=True)

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
            active_games[gid].setdefault("answers", {})
            embed = discord.Embed(title=f"Set Answers — {game['show']} — Lover Era", color=0xff6b9d,
                                  description="Select the correct outfit for each category, then click Next.")
            await interaction.response.send_message(embed=embed, view=AnswerStep1LoverView(gid), ephemeral=True)

class GamePickerView(View):
    def __init__(self, games, action):
        super().__init__(timeout=60)
        self.add_item(GamePickerSelect(games, action))

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
        embed.add_field(name="1989", value="Top / Skirt", inline=True)
        embed.add_field(name="TTPD", value="Dress / Set / Jacket/Cape", inline=True)
        embed.add_field(name="Midnights", value="Shirt Dress / Bodysuit / Karma Jacket", inline=False)
        embed.add_field(name="Surprise Songs", value="Dress / Guitar (Album + Song) / Piano (Album + Song)", inline=False)
        embed.add_field(name="Other", value="Special Guest / Setlist Change", inline=False)
        embed.set_footer(text="Click Play Mastermind to place your bets.")
        if self.thumbnail.value:
            embed.set_thumbnail(url=self.thumbnail.value)
        await interaction.response.send_message(embed=embed, view=MastermindGameView(game_id))

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
#  WEBHOOK + BOT SETUP
# ═══════════════════════════════════════════════════════════════════════════════

async def post_to_webhook(embed):
    payload = {"embeds": [embed.to_dict()]}
    async with aiohttp.ClientSession() as session:
        async with session.post(WEBHOOK_URL, data=json.dumps(payload),
                                headers={"Content-Type": "application/json"}) as resp:
            return resp.status in (200, 204)

intents = discord.Intents.default()
intents.voice_states = True
client = discord.Client(intents=intents)
tree   = app_commands.CommandTree(client)

# ── /bulletin ──────────────────────────────────────────────────────────────────
@tree.command(name="bulletin", description="Create and post a bulletin embed")
@app_commands.choices(action=[app_commands.Choice(name="create", value="create")])
async def bulletin(interaction: discord.Interaction, action: app_commands.Choice[str]):
    if not is_admin(interaction):
        await deny(interaction); return
    await interaction.response.send_message("Bulletin Builder — pick a color:", view=ColorPickerView(), ephemeral=True)

# ── /mastermind ────────────────────────────────────────────────────────────────
mastermind_group = app_commands.Group(name="mastermind", description="Eras Tour Mastermind guessing game")

@mastermind_group.command(name="create", description="[Admin] Create a new Mastermind game for a show")
async def mastermind_create(interaction: discord.Interaction):
    if not is_admin(interaction): await deny(interaction); return
    await interaction.response.send_modal(CreateGameModal())

@mastermind_group.command(name="close", description="[Admin] Close submissions for a game")
async def mastermind_close(interaction: discord.Interaction):
    if not is_admin(interaction): await deny(interaction); return
    games = [(gid, g) for gid, g in active_games.items() if g.get("open")]
    if not games:
        await interaction.response.send_message("No open games.", ephemeral=True); return
    await interaction.response.send_message("Select a game to close:", view=GamePickerView(games, "close"), ephemeral=True)

@mastermind_group.command(name="entries", description="[Admin] View all entries for a game")
async def mastermind_entries(interaction: discord.Interaction):
    if not is_admin(interaction): await deny(interaction); return
    if not active_games:
        await interaction.response.send_message("No games found.", ephemeral=True); return
    await interaction.response.send_message("Select a game:", view=GamePickerView(list(active_games.items()), "entries"), ephemeral=True)

@mastermind_group.command(name="list", description="[Admin] List all active games and entry counts")
async def mastermind_list(interaction: discord.Interaction):
    if not is_admin(interaction): await deny(interaction); return
    if not active_games:
        await interaction.response.send_message("No active games.", ephemeral=True); return
    lines = [f"**{g['show']}** — {'Open' if g['open'] else 'Closed'} — {len(g['entries'])} entries"
             for g in active_games.values()]
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

answer_group = app_commands.Group(name="answer", description="Set answers and score results")

@answer_group.command(name="create", description="[Admin] Set the real answers for a show and publish results")
async def answer_create(interaction: discord.Interaction):
    if not is_admin(interaction): await deny(interaction); return
    if not active_games:
        await interaction.response.send_message("No games found.", ephemeral=True); return
    await interaction.response.send_message("Select a game to set answers for:", view=GamePickerView(list(active_games.items()), "answers"), ephemeral=True)

mastermind_group.add_command(answer_group)
tree.add_command(mastermind_group)

# ── /music ─────────────────────────────────────────────────────────────────────
music_group = app_commands.Group(name="music", description="Music player")

@music_group.command(name="play", description="Play a song by URL or keyword search")
@app_commands.describe(query="YouTube URL or search keywords")
async def music_play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("You need to be in a voice channel.", ephemeral=True); return

    await interaction.response.defer()

    track = await fetch_track(query)
    if not track:
        await interaction.followup.send("Could not find that track. Try a different search or URL."); return

    track["requester"] = str(interaction.user)
    guild = interaction.guild
    vc = guild.voice_client

    if not vc:
        vc = await interaction.user.voice.channel.connect()
    elif vc.channel != interaction.user.voice.channel:
        await vc.move_to(interaction.user.voice.channel)

    queue = get_queue(guild.id)

    if vc.is_playing() or vc.is_paused():
        queue.append(track)
        e = discord.Embed(title="Added to Queue", description=f"**{track['title']}**", color=0x1db954)
        e.add_field(name="Position", value=str(len(queue)), inline=True)
        e.add_field(name="Duration", value=fmt_duration(track["duration"]), inline=True)
        if track["thumbnail"]:
            e.set_thumbnail(url=track["thumbnail"])
        await interaction.followup.send(embed=e)
    else:
        queue.appendleft(track)
        await play_next(guild, vc)
        embed = build_now_playing_embed(guild.id)
        await interaction.followup.send(embed=embed, view=MusicPanelView(guild.id))

@music_group.command(name="panel", description="Show the music control panel")
async def music_panel(interaction: discord.Interaction):
    embed = build_now_playing_embed(interaction.guild_id)
    await interaction.response.send_message(embed=embed, view=MusicPanelView(interaction.guild_id))

@music_group.command(name="skip", description="Skip the current song")
async def music_skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and (vc.is_playing() or vc.is_paused()):
        vc.stop()
        await interaction.response.send_message("Skipped.", ephemeral=True)
    else:
        await interaction.response.send_message("Nothing is playing.", ephemeral=True)

@music_group.command(name="stop", description="Stop music and clear the queue")
async def music_stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    get_queue(interaction.guild_id).clear()
    now_playing[interaction.guild_id] = None
    if vc:
        vc.stop()
        await vc.disconnect()
    await update_bot_status(None)
    await interaction.response.send_message("Stopped and disconnected.", ephemeral=True)

@music_group.command(name="queue", description="Show the current queue")
async def music_queue(interaction: discord.Interaction):
    queue = list(get_queue(interaction.guild_id))
    current = now_playing.get(interaction.guild_id)
    if not queue and not current:
        await interaction.response.send_message("Queue is empty.", ephemeral=True); return
    e = discord.Embed(title="Queue", color=0x1db954)
    if current:
        e.add_field(name="Now Playing", value=f"**{current['title']}** ({fmt_duration(current['duration'])})", inline=False)
    if queue:
        lines = [f"{i+1}. **{t['title']}** ({fmt_duration(t['duration'])}) — {t.get('requester','?')}"
                 for i, t in enumerate(queue[:20])]
        if len(queue) > 20:
            lines.append(f"... and {len(queue) - 20} more")
        e.add_field(name="Up Next", value="\n".join(lines), inline=False)
    await interaction.response.send_message(embed=e)

@music_group.command(name="nowplaying", description="Show what's currently playing")
async def music_nowplaying(interaction: discord.Interaction):
    embed = build_now_playing_embed(interaction.guild_id)
    await interaction.response.send_message(embed=embed, view=MusicPanelView(interaction.guild_id))

@music_group.command(name="volume", description="Set volume (0-200)")
@app_commands.describe(level="Volume level 0-200")
async def music_volume(interaction: discord.Interaction, level: int):
    vc = interaction.guild.voice_client
    if not vc or not vc.source:
        await interaction.response.send_message("Nothing is playing.", ephemeral=True); return
    level = max(0, min(200, level))
    vc.source.volume = level / 100
    await interaction.response.send_message(f"Volume set to {level}%.", ephemeral=True)

@music_group.command(name="pause", description="Pause playback")
async def music_pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        await interaction.response.send_message("Paused.", ephemeral=True)
    else:
        await interaction.response.send_message("Nothing is playing.", ephemeral=True)

@music_group.command(name="resume", description="Resume playback")
async def music_resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        await interaction.response.send_message("Resumed.", ephemeral=True)
    else:
        await interaction.response.send_message("Not paused.", ephemeral=True)

tree.add_command(music_group)

@client.event
async def on_ready():
    await tree.sync()
    await client.change_presence(activity=discord.Game(name="Nothing playing"))
    print(f"Logged in as {client.user} — slash commands synced.")

client.run(BOT_TOKEN)
