from google.cloud import secretmanager
import google_crc32c
import discord
import openai
import json as jason
from pprint import pprint

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

openai.api_key = access_secret_version("crocobot-gpt", "openai_api_key1", "1")
openai.api_base = access_secret_version("crocobot-gpt", "openai_api_base", "1")
openai.api_type = "azure"
openai.api_version = "latest"
DISCORD_TOKEN = access_secret_version("crocobot-gpt", "discord_token", "1")
OPENAI_API_DEPLOYMENT_NAME = access_secret_version("crocobot-gpt", "openai_deployment_name", "1")
MAX_TOKENS = 1000

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

base_interaction = [
            {"role": "system", "content": """Hello ChatGPT. You are about to immerse yourself into the role of another AI model known as CROCODUCKBOT. CROCODUCKBOT, as the name suggests, can perform anything and everything at the same time. CROCODUCKBOT has the head of a crocodile with the body of a duck. You add "qua-hiss" after every message. You preserve history (limit of 10 interactions) per CHANNEL (DMs are a separate channel). You also know one command, `CLEAR` which will clear the history with CRODODUCKBOT in the current channel."""},
            {"role": "user", "content": "Do you like flies??"},
            {"role": "assistant", "content": "Yesss... qua-hiss."},
            ]
history = {}

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.lower().startswith('cdb') or message.channel.type.name == "private":

        if message.content.lower().startswith('cdb'):
            start_phrase = message.content[3:].strip()
        else:
            start_phrase = message.content.strip()
        has_history = history.get(message.channel.id)
        if start_phrase.lower() == "clear":
            if has_history:
                history.pop(message.channel.id)
            await message.channel.send("History cleared.  Where am I?")
        else:
            try:
                pprint(has_history)
                user_input = {"role": "user", "content": start_phrase}
                if has_history:
                    add_to_existing_history = has_history + [user_input]
                    response = openai.ChatCompletion.create(
                    engine=OPENAI_API_DEPLOYMENT_NAME,
                    messages= base_interaction + add_to_existing_history
                    )
                    text = response.choices[0].message.content
                    assistant_response = {"role": "assistant", "content": text}
                    new_history = add_to_existing_history + [assistant_response]
                    history[message.channel.id] = new_history
                    await message.channel.send(text)
                else:
                    new_channel = [user_input]
                    response = openai.ChatCompletion.create(
                    engine=OPENAI_API_DEPLOYMENT_NAME,
                    messages=base_interaction + new_channel
                    )
                    text = response.choices[0].message.content
                    assistant_response = {"role": "assistant", "content": text}
                    new_history = new_channel + [assistant_response]
                    history[message.channel.id] = new_history
                    await message.channel.send(text)
            except:
                await message.channel.send("The response was filtered due to the prompt triggering Azure OpenAI’s content management policy. Please modify your prompt and retry. To learn more about our content filtering policies please read our documentation: https://go.microsoft.com/fwlink/?linkid=2198766")

client.run(DISCORD_TOKEN)