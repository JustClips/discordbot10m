import os
import discord
import re
import requests
import json
from urllib.parse import unquote

TOKEN = os.getenv("DISCORD_TOKEN")

# Accept multiple channel IDs
CHANNEL_ID_ENV = os.getenv("CHANNEL_ID", "1234567890")
CHANNEL_IDS = [int(cid.strip()) for cid in CHANNEL_ID_ENV.split(",") if cid.strip()]

# Accept multiple webhook URLs
WEBHOOK_URL_ENV = os.getenv("WEBHOOK_URL", "")
WEBHOOK_URLS = [url.strip() for url in WEBHOOK_URL_ENV.split(",") if url.strip()]

BACKEND_URL = os.getenv("BACKEND_URL")

client = discord.Client()

def clean_field(text):
    if not text:
        return text
    text = re.sub(r'```([^`]+)```', r'\1', text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    return text.strip()

def parse_info_from_embed(message):
    info = {
        "name": None,
        "money": None,
        "players": None,
        "jobid_mobile": None,
        "jobid_pc": None,
        "jobid_ios": None,
        "instanceid": None,
        "placeid": "109983668079237"
    }
    for embed in message.embeds:
        for field in embed.fields:
            field_name = field.name.lower().strip()
            field_value = clean_field(field.value)
            if "name" in field_name:
                info["name"] = field_value
            elif "money" in field_name or "per sec" in field_name:
                info["money"] = field_value
            elif "players" in field_name:
                info["players"] = field_value
            elif "id (mobile)" in field_name or "mobile" in field_name:
                info["jobid_mobile"] = field_value
            elif "id (pc)" in field_name or "(pc)" in field_name:
                info["jobid_pc"] = field_value
            elif "id (ios)" in field_name or "(ios)" in field_name:
                info["jobid_ios"] = field_value
    info["instanceid"] = (
        info["jobid_pc"] if info["jobid_pc"] else
        info["jobid_ios"] if info["jobid_ios"] else
        info["jobid_mobile"] if info["jobid_mobile"] else
        None
    )
    return info

def parse_info_from_content(msg):
    name = re.search(r'🏷️\s*Name\s*\n([^\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    if not name:
        name = re.search(r':settings:\s*Name\s*\n([^\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    if not name:
        name = re.search(r'<:settings:\d+>\s*Name\s*\n([^\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    money = re.search(r'💰\s*Money per sec\s*\n([^\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    if not money:
        money = re.search(r':media:\s*Money per sec\s*\n([^\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    if not money:
        money = re.search(r'<:media:\d+>\s*Money per sec\s*\n([^\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    players = re.search(r'👥\s*Players\s*\n([^\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    if not players:
        players = re.search(r':member:\s*Players\s*\n([^\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    if not players:
        players = re.search(r'<:member:\d+>\s*Players\s*\n([^\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    jobid_mobile = re.search(r'(?:Job\s*)?ID\s*\(Mobile\)\s*\n([A-Za-z0-9\-+/=`\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    jobid_pc = re.search(r'(?:Job\s*)?ID\s*\(PC\)\s*\n([A-Za-z0-9\-+/=`\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    jobid_ios = re.search(r'(?:Job\s*)?ID\s*\(iOS\)\s*\n([A-Za-z0-9\-+/=`\n]+)', msg, re.MULTILINE | re.IGNORECASE)
    jobid_mobile_clean = clean_field(jobid_mobile.group(1)) if jobid_mobile else None
    jobid_ios_clean = clean_field(jobid_ios.group(1)) if jobid_ios else None  
    jobid_pc_clean = clean_field(jobid_pc.group(1)) if jobid_pc else None
    return {
        "name": clean_field(name.group(1)) if name else None,
        "money": clean_field(money.group(1)) if money else None,
        "players": clean_field(players.group(1)) if players else None,
        "jobid_mobile": jobid_mobile_clean,
        "jobid_ios": jobid_ios_clean,
        "jobid_pc": jobid_pc_clean,
        "instanceid": (
            jobid_pc_clean if jobid_pc_clean else
            jobid_ios_clean if jobid_ios_clean else
            jobid_mobile_clean if jobid_mobile_clean else
            None
        ),
        "placeid": "109983668079237"
    }

def get_message_full_content(message):
    parts = []
    if message.content and message.content.strip():
        parts.append(message.content)
    for embed in message.embeds:
        if embed.title:
            parts.append(embed.title)
        if embed.description:
            parts.append(embed.description)
        for field in getattr(embed, "fields", []):
            parts.append(f"{field.name}\n{field.value}")
    for att in message.attachments:
        parts.append(att.url)
    return "\n".join(parts) if parts else "(no content)"

def build_embed(info):
    fields = []
    if info["name"]:
        fields.append({
            "name": "🏷️ Name",
            "value": info['name'],
            "inline": False
        })
    if info["money"]:
        fields.append({
            "name": "💰 Money per sec",
            "value": info['money'],
            "inline": False
        })
    if info["players"]:
        fields.append({
            "name": "👥 Players",
            "value": info['players'],
            "inline": False
        })
    if info["instanceid"]:
        clean_jobid = str(info["instanceid"]).strip()
        clean_placeid = str(info["placeid"]).strip()
        simple_script = f'game:GetService("TeleportService"):TeleportToPlaceInstance({clean_placeid}, "{clean_jobid}", game.Players.LocalPlayer)'
        fields.append({
            "name": "🚀 Quick Join Script",
            "value": f"```lua\n{simple_script}\n```",
            "inline": False
        })
        detailed_script = f"""-- Teleport Script
local TeleportService = game:GetService("TeleportService")
local Players = game:GetService("Players")
local localPlayer = Players.LocalPlayer

local placeId = {clean_placeid}
local jobId = "{clean_jobid}"

print("Attempting to teleport to Place ID: " .. tostring(placeId))
print("Job ID: " .. jobId)

local success, err = pcall(function()
    TeleportService:TeleportToPlaceInstance(placeId, jobId, localPlayer)
end)

if not success then
    warn("Teleport failed: " .. tostring(err))
else
    print("Teleporting to server...")
end"""
        fields.append({
            "name": "📜 Detailed Join Script",
            "value": f"```lua\n{detailed_script}\n```",
            "inline": False
        })
    if info["jobid_mobile"]:
        fields.append({
            "name": "🆔 Job ID (Mobile)",
            "value": f"`{info['jobid_mobile']}`",
            "inline": False
        })
    if info["jobid_pc"] and info["jobid_pc"] != info["jobid_mobile"]:
        fields.append({
            "name": "🆔 Job ID (PC)",
            "value": f"`{info['jobid_pc']}`",
            "inline": False
        })
    if info["jobid_ios"] and info["jobid_ios"] != info["jobid_mobile"] and info["jobid_ios"] != info["jobid_pc"]:
        fields.append({
            "name": "🆔 Job ID (iOS)",
            "value": f"`{info['jobid_ios']}`",
            "inline": False
        })
    embed = {
        "title": "Eps1lon Hub Notifier",
        "color": 0x5865F2,
        "fields": fields
    }
    return {"embeds": [embed]}

def send_to_backend(info):
    if not BACKEND_URL:
        print("⚠️ BACKEND_URL not configured - skipping backend send")
        return
    if not info["name"]:
        print("Skipping backend send - missing name")
        return
    payload = {
        "name": info["name"],
        "serverId": str(info["placeid"]),
        "jobId": str(info["instanceid"]) if info["instanceid"] else "",
        "instanceId": str(info["instanceid"]) if info["instanceid"] else "",
        "players": info["players"],
        "moneyPerSec": info["money"]
    }
    try:
        response = requests.post(BACKEND_URL, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"✅ Sent to backend: {info['name']} -> {payload.get('serverId','(none)')[:8]}... ({info['players']})")
        elif response.status_code == 429:
            print(f"⚠️ Rate limited for backend: {info['name']}")
        else:
            print(f"❌ Backend error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Failed to send to backend: {e}")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    print(f'Monitoring channels: {CHANNEL_IDS}')
    if WEBHOOK_URLS:
        print('✅ Webhook URLs configured: ' + ", ".join(WEBHOOK_URLS))
    else:
        print('⚠️ WEBHOOK_URL not configured - webhook sends will be skipped')
    if BACKEND_URL:
        print('✅ Backend URL configured')
    else:
        print('⚠️ BACKEND_URL not configured - backend sends will be skipped')

@client.event
async def on_message(message):
    if message.channel.id not in CHANNEL_IDS:
        return
    if message.embeds:
        info = parse_info_from_embed(message)
    else:
        full_content = get_message_full_content(message)
        info = parse_info_from_content(full_content)
    print(f"Debug - Final parsed info: name='{info['name']}', money='{info['money']}', players='{info['players']}', instanceid='{info['instanceid']}'")
    if info["name"] and info["money"] and info["players"]:
        if WEBHOOK_URLS:
            embed_payload = build_embed(info)
            for webhook_url in WEBHOOK_URLS:
                try:
                    requests.post(webhook_url, json=embed_payload)
                    print(f"✅ Sent embed to webhook ({webhook_url}) for: {info['name']}")
                except Exception as e:
                    print(f"❌ Failed to send embed to webhook ({webhook_url}): {e}")
        else:
            print("⚠️ Webhook URLs not configured - skipping webhook send")
        send_to_backend(info)
    else:
        if WEBHOOK_URLS:
            full_content = get_message_full_content(message)
            for webhook_url in WEBHOOK_URLS:
                try:
                    requests.post(webhook_url, json={"content": full_content})
                    print(f"⚠️ Sent plain text to webhook ({webhook_url}) (missing fields)")
                except Exception as e:
                    print(f"❌ Failed to send plain text to webhook ({webhook_url}): {e}")
        else:
            print("⚠️ Webhook URLs not configured - skipping fallback webhook send")

client.run(TOKEN)
