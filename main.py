import discord
import os
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


TEST_GUILD = discord.Object(id=int(os.getenv('DISCORD_SERVER_ID'))) 


@client.event
async def on_ready():
    print(f'Bot {client.user} está online!')
    await tree.sync(guild=TEST_GUILD)
    print('Comandos sincronizados.')


@tree.command(
    name="ping",
    description="Responde com Pong!",
    guild=TEST_GUILD 
)
async def ping_command(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")

client.run(TOKEN)