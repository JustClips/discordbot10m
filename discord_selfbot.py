import os
import discord
import re
import requests
import threading
import json
from discord.ext import tasks

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_IDS = [int(cid.strip()) for cid in os.getenv("CHANNEL_ID", "1234567890").split(",")]
WEBHOOK_URLS = [url.strip() for url in os.getenv("WEBHOOK_URLS", "").split(",") if url.strip()]
BACKEND_URL = os.getenv("BACKEND_URL")

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Store parsed messages to be sent later
pending_updates = []

def clean_field(text):
    if not text:
        return text
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'^`{3,}([^\n]*?)`{3,}$', r'\1', text, flags=re.DOTALL)
    text = text.replace('`', '').strip()
    return text

def parse_embed_fields(message):
    if not message.embeds or not hasattr(message.embeds[0], 'fields'):
        return None
    embed = message.embeds[0]
    fields = {f.name.strip().lower(): clean_field(f.value) for f in embed.fields}
    name = fields.get("🏷️ name") or fields.get("name")
    money = fields.get("💰 money per sec") or fields.get("money per sec")
    players = fields.get("👥 players") or fields.get("players")
    jobid = fields.get("🆔 job id (pc)") or fields.get("job id (pc)") or fields.get("job id")
    if jobid:
        jobid = jobid.replace("\n", "").strip()
    return dict(name=name, money=money, players=players, jobid=jobid)

def build_embed(info):
    fields = []
    if info["name"]:
        fields.append({"name": "🏷️ Name", "value": f"**{info['name']}**", "inline": False})
    if info["money"]:
        fields.append({"name": "💰 Money per sec", "value": f"**{info['money']}**", "inline": True})
    if info["players"]:
        fields.append({"name": "👥 Players", "value": f"**{info['players']}**", "inline": True})
    if info["jobid"]:
        fields.append({"name": "🆔 Job ID (PC)", "value": f"```{info['jobid']}```", "inline": False})
    return {
        "title": "Brainrot Notify | notasnek",
        "color": 0x8e44ad,
        "fields": fields,
        "footer": {"text": "Made by notasnek"}
    }

def send_to_webhooks(payload):
    def send(url, payload):
        try:
            r = requests.post(url, json={"embeds": [payload]}, timeout=10)
            print("✅ Webhook sent" if r.status_code in [200,204] else f"❌ Webhook error {r.status_code}")
        except Exception as e:
            print(f"❌ Webhook exception: {e}")
    for url in WEBHOOK_URLS:
        threading.Thread(target=send, args=(url, payload)).start()

def send_to_backend(info):
    server_id = "brainrot"
    if not info["name"] or not info["jobid"]:
        print("Skipping backend send - missing name or jobid")
        return
    payload = {
        "name": info["name"],
        "serverId": server_id,
        "jobId": info["jobid"],
        "moneyPerSec": info.get("money", "unknown"),
        "players": info.get("players", "unknown")
    }
    try:
        r = requests.post(BACKEND_URL, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"✅ Sent to backend: {info['name']}")
        else:
            print(f"❌ Backend error {r.status_code}: {r.text}")
    except Exception as e:
        print(f"❌ Failed to send to backend: {e}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    print(f'Watching channels: {CHANNEL_IDS}')
    send_loop.start()

@client.event
async def on_message(message):
    if message.channel.id not in CHANNEL_IDS:
        return

    try:
        if message.content and message.content.strip().startswith("[") and message.content.strip().endswith("]"):
            servers = json.loads(message.content)
            if isinstance(servers, list) and all(isinstance(x, dict) for x in servers):
                print(f"Detected servers list with {len(servers)} servers. Sending to backend.")
                for s in servers:
                    pending_updates.append(s)
                return
    except Exception as e:
        print(f"❌ Failed to parse servers list: {e}")

    info = parse_embed_fields(message)
    if info and info["name"] and info["jobid"]:
        pending_updates.append(info)
        print(f"✅ Queued: {info['name']}")
    else:
        print("⚠️ Missing required fields. Skipping.")

@tasks.loop(seconds=0.5)
async def send_loop():
    global pending_updates
    if not pending_updates:
        return

    # Copy and clear the list to avoid race conditions
    to_send = pending_updates[:]
    pending_updates.clear()

    for info in to_send:
        if "jobId" in info:  # Already a full server object from list
            # Send directly
            try:
                r = requests.post(BACKEND_URL, json=info, timeout=10)
                if r.status_code == 200:
                    print(f"✅ Sent server to backend: {info['name']}")
                else:
                    print(f"❌ Backend error {r.status_code}")
            except Exception as e:
                print(f"❌ Failed to send to backend: {e}")
        else:
            # Regular parsed embed
            embed_payload = build_embed(info)
            send_to_webhooks(embed_payload)
            send_to_backend(info)

client.run(TOKEN)
