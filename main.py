import discord
from discord import app_commands
from discord.ui import Modal, TextInput, View, Button, Select
import aiohttp
import json
import os

# ─── CONFIG ───────────────────────────────────────────────────────────────────
WEBHOOK_URL = "https://discord.com/api/webhooks/1475369638001901761/juynubLrFgKHt9cG5E4tGCfj5DZdO5JDPdhu8pREGVEBEVxFCRZxYvwqisLTiyqfWxoa"
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# ──────────────────────────────────────────────────────────────────────────────


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

# ─── MODAL ────────────────────────────────────────────────────────────────────
class BulletinModal(Modal, title="📋 Create Bulletin"):
    embed_title = TextInput(
        label="Title",
        placeholder="e.g. Server Announcement",
        max_length=256,
        required=True,
    )
    description = TextInput(
        label="Description",
        placeholder="Main body of your bulletin...",
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=True,
    )
    footer_text = TextInput(
        label="Footer",
        placeholder="e.g. Posted by Staff Team",
        required=False,
        max_length=2048,
    )
    image_url = TextInput(
        label="Image URL (optional)",
        placeholder="https://example.com/image.png",
        required=False,
    )
    thumbnail_url = TextInput(
        label="Thumbnail URL (optional)",
        placeholder="https://example.com/thumb.png",
        required=False,
    )

    def __init__(self, color: int = 0x3498db):
        super().__init__()
        self.chosen_color = color

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=self.embed_title.value,
            description=self.description.value,
            color=self.chosen_color,
        )
        if self.footer_text.value:
            embed.set_footer(text=self.footer_text.value)
        if self.image_url.value:
            embed.set_image(url=self.image_url.value)
        if self.thumbnail_url.value:
            embed.set_thumbnail(url=self.thumbnail_url.value)

        # Preview first
        view = ConfirmView(embed)
        await interaction.response.send_message(
            "**📋 Preview — does this look good?**",
            embed=embed,
            view=view,
            ephemeral=True,
        )


# ─── COLOR PICKER VIEW ────────────────────────────────────────────────────────
class ColorSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=name, value=str(hex_val), description=f"#{hex_val:06X}")
            for name, hex_val in COLORS.items()
        ]
        super().__init__(
            placeholder="🎨 Pick an embed color…",
            options=options,
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        color = int(self.values[0]) & 0xFFFFFF
        modal = BulletinModal(color=color)
        await interaction.response.send_modal(modal)


class ColorPickerView(View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(ColorSelect())


# ─── CONFIRM VIEW ─────────────────────────────────────────────────────────────
class ConfirmView(View):
    def __init__(self, embed: discord.Embed):
        super().__init__(timeout=180)
        self.embed = embed

    @discord.ui.button(label="✅ Post Bulletin", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer(ephemeral=True)
        success = await post_to_webhook(self.embed)
        if success:
            await interaction.followup.send("✅ Bulletin posted to the webhook!", ephemeral=True)
        else:
            await interaction.followup.send("❌ Failed to post. Check the webhook URL.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="🗑️ Cancel", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Bulletin cancelled.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="✏️ Edit Again", style=discord.ButtonStyle.secondary)
    async def edit(self, interaction: discord.Interaction, button: Button):
        color = self.embed.color.value if self.embed.color else 0x3498db
        modal = BulletinModal(color=color)
        # Pre-fill isn't natively supported in Discord modals, but we can re-open
        await interaction.response.send_modal(modal)
        self.stop()


# ─── WEBHOOK SENDER ───────────────────────────────────────────────────────────
async def post_to_webhook(embed: discord.Embed) -> bool:
    payload = {"embeds": [embed.to_dict()]}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        ) as resp:
            return resp.status in (200, 204)


# ─── BOT SETUP ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
client  = discord.Client(intents=intents)
tree    = app_commands.CommandTree(client)


@tree.command(name="bulletin", description="Create and post a bulletin embed")
@app_commands.describe(action="Action to perform")
@app_commands.choices(action=[
    app_commands.Choice(name="create", value="create"),
])
async def bulletin(interaction: discord.Interaction, action: app_commands.Choice[str]):
    if action.value == "create":
        view = ColorPickerView()
        await interaction.response.send_message(
            "**📋 Bulletin Builder**\nFirst, pick a color for your embed:",
            view=view,
            ephemeral=True,
        )


@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {client.user} — slash commands synced.")


client.run(BOT_TOKEN)
