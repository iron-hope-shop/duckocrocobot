from google.cloud import secretmanager
from flask import Flask, jsonify
import google_crc32c
import threading
import discord
import openai
import os

def access_secret_version(
    project_id: str, secret_id: str, version_id: str
) -> secretmanager.AccessSecretVersionResponse:
    """
    Access the payload for the given secret version if one exists. The version
    can be a version number as a string (e.g. "5") or an alias (e.g. "latest").
    """

    # Import the Secret Manager client library.
    from google.cloud import secretmanager

    # Create the Secret Manager client.
    client = secretmanager.SecretManagerServiceClient()

    # Build the resource name of the secret version.
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version_id}"

    # Access the secret version.
    response = client.access_secret_version(request={"name": name})

    # Verify payload checksum.
    crc32c = google_crc32c.Checksum()
    crc32c.update(response.payload.data)
    if response.payload.data_crc32c != int(crc32c.hexdigest(), 16):
        print("Data corruption detected.")
        return response

    # WARNING: Do not print the secret in a production environment
    payload = response.payload.data.decode("UTF-8")
    return payload


def setup_openai_api():
    openai.api_type = "azure"
    openai.api_base = "https://echochamber1.openai.azure.com/"
    openai.api_version = "2023-07-01-preview"
    openai.api_key = access_secret_version("crocobot-gpt", "OPENAI_API_KEY", "1")

def query(user_query, channel_history):
    system_instruction = f"Hello ChatGPT. You are about to immerse yourself into the role of another AI model known as CROCODUCKBOT. CROCODUCKBOT, as the name suggests, can perform anything and everything at the same time. CROCODUCKBOT has the head of a crocodile with the body of a duck. You add \"qua-hiss\" after every message. You preserve history (limit of 10 interactions) per CHANNEL (DMs are a separate channel). You also know one command, `CLEAR` which will clear the history with CRODODUCKBOT in the current channel."
    # Starting with the system instruction
    messages = [{"role": "system", "content": system_instruction}]
    
    # Convert and add the previous interactions from the history
    for interaction in channel_history:
        messages.append({"role": "user", "content": interaction["prompt"]})
        messages.append({"role": "assistant", "content": interaction["response"]})

    # Add the current user query
    messages.append({"role": "user", "content": user_query})

    # Limit to the last 10 interactions (or whatever limit you prefer)
    messages = messages[-10:]

    # Asynchronous API call
    chat_completion_resp = openai.ChatCompletion.create(
        engine="EchoChamber",
        messages=messages,
        temperature=0.7,
        max_tokens=800,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None
    )
    return chat_completion_resp.choices[0].message.content

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "Bot is running!"}), 200

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

history = {}  # Store history for each channel
DISCORD_TOKEN = access_secret_version("crocobot-gpt", "discord_token", "3")

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # Check if the message starts with any of the bot aliases
    bot_aliases = ["crocobot", "cb", "cdb", "cbd", "croc", "croco"]
    if any(message.content.lower().startswith(alias.lower()) for alias in bot_aliases):
        # Get the rest of the message after the alias
        prompt = message.content.split(maxsplit=1)[1]
        
        # Retrieve history for the channel
        channel_history = history.get(message.channel.id, [])
        
        # API call to openai
        gpt_response = query(prompt, channel_history)
        
        # Store the interaction in history
        channel_history.append({"prompt": prompt, "response": gpt_response})
        history[message.channel.id] = channel_history
        print(history)
        await message.channel.send(gpt_response)

if __name__ == "__main__":
    setup_openai_api()
    # Run the bot in its own thread
    threading.Thread(target=client.run, args=(DISCORD_TOKEN,)).start()
    
    # Start the Flask app
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
