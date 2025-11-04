import discord
import os
import datetime
from discord import app_commands
from discord.app_commands import Choice
from dotenv import load_dotenv


from database import init_db, close_db, Desafio 

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

TEST_GUILD = discord.Object(id=int(os.getenv("DISCORD_SERVER_ID"))) 


@client.event
async def on_ready():
    
    await init_db() 
    
    print(f'Bot {client.user} está online!')
    await tree.sync(guild=TEST_GUILD)
    print('Comandos sincronizados.')

@client.event
async def on_shutdown():
    await close_db()


@tree.command(
    name="ping",
    description="Responde com Pong!",
    guild=TEST_GUILD
)
async def ping_command(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")


@tree.command(
    name="criar-desafio",
    description="Cria um novo desafio de programação.",
    guild=TEST_GUILD
)
@app_commands.describe(
    titulo="O título do desafio (ex: API de Finanças Pessoais)",
    descricao="A descrição completa do que deve ser feito (use '|' para quebra de linha)",
    nivel="O nível de dificuldade do desafio",
    dias_para_concluir="Quantos dias os membros terão para submeter (ex: 7)"
)
@app_commands.choices(nivel=[
    Choice(name='Júnior', value='junior'),
    Choice(name='Pleno', value='pleno'),
    Choice(name='Sênior', value='senior'),
])
@app_commands.checks.has_permissions(administrator=True)
async def criar_desafio(
    interaction: discord.Interaction,
    titulo: str,
    descricao: str,
    nivel: Choice[str],
    dias_para_concluir: int
):
    await interaction.response.defer(ephemeral=True)

    data_fim = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=dias_para_concluir)
    
    descricao_formatada = descricao.replace('|', '\n')

    try:
        novo_desafio = await Desafio.create(
            titulo=titulo,
            descricao=descricao_formatada,
            nivel=nivel.value, 
            data_fim_submissao=data_fim
        )
        
    except Exception as e:
        print(f"Erro ao salvar no DB: {e}")
        await interaction.followup.send(f"❌ Erro ao criar o desafio no banco de dados: {e}")
        return

    canal_desafios = client.get_channel(int(os.getenv("DISCORD_CHANNEL_ID")))

    if canal_desafios:
        embed = discord.Embed(
            title=f"🚀 Novo Desafio: {titulo} (Nível: {nivel.name})",
            description=descricao_formatada,
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Prazo de Submissão",
            value=f"Até <t:{int(data_fim.timestamp())}:F>"
        )
        embed.set_footer(text=f"ID do Desafio: {novo_desafio.id} | Use /submeter para participar!")

        await canal_desafios.send(content="@everyone Novo desafio lançado!", embed=embed)
        
        await interaction.followup.send(f"✅ Desafio '{titulo}' (ID: {novo_desafio.id}) criado com sucesso e anunciado em {canal_desafios.mention}!")
    
    else:
        await interaction.followup.send(f"⚠️ Desafio criado no DB (ID: {novo_desafio.id}), mas não encontrei o canal de anúncios. Verifique o ID.")

@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "Você não tem permissão para usar este comando.",
            ephemeral=True
        )
    else:
        print(error)
        await interaction.response.send_message(
            f"Ocorreu um erro: {error}",
            ephemeral=True
        )

client.run(TOKEN)