import discord
import os
import datetime
from discord import app_commands
from discord.app_commands import Choice
from dotenv import load_dotenv


from database import Submissao, Usuario, Voto, init_db, close_db, Desafio 

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PONTOS_POR_VOTO_COMUNIDADE = 15
PONTOS_POR_VOTO_JURADO = 30

NOME_CARGO_JURADO = "Jurado"


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

## INICIANDO COMANDOS ##

## CRIAR DESAFIO ##

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

## SUBMETER SOLUÇÃO ##

@tree.command(
    name="submeter",
    description="Envia sua solução para um desafio aberto.",
    guild=TEST_GUILD
)

@app_commands.describe(
    id_desafio="O ID numérico do desafio (veja no #canal-desafios)",
    link_codigo="O link para seu código (GitHub Gist, Pastebin, etc.)"
)
async def submeter(
    interaction: discord.Interaction,
    id_desafio: int,
    link_codigo: str
):
    await interaction.response.defer(ephemeral=True)

    try:
        desafio = await Desafio.get(id=id_desafio)

    except Exception: 
        await interaction.followup.send("❌ **Erro:** Desafio com este ID não encontrado.")
        return

    if desafio.status != Desafio.Status.ABERTO:
        await interaction.followup.send(f"❌ **Erro:** Este desafio não está mais aceitando submissões (Status: {desafio.status}).")
        return

    agora = datetime.datetime.now(datetime.timezone.utc)
    if agora > desafio.data_fim_submissao:
        await interaction.followup.send("❌ **Erro:** O prazo para este desafio já encerrou.")
        desafio.status = Desafio.Status.VOTACAO
        await desafio.save()
        return

   
    if not link_codigo.startswith("http://") and not link_codigo.startswith("https://"):
        await interaction.followup.send("❌ **Erro:** O link do código parece inválido. Deve começar com `http://` ou `https://`.")
        return

    try:
        usuario_db, criado = await Usuario.get_or_create(
            discord_id=interaction.user.id,
            defaults={"username": interaction.user.name}
        )
        
        
        submissao, criada = await Submissao.update_or_create(
            desafio=desafio,
            usuario=usuario_db,
            defaults={"link_codigo": link_codigo, "data_submissao": agora}
        )

        if criada:
            await interaction.followup.send(
                f"✅ **Submissão recebida!**\n"
                f"Sua solução para o desafio '{desafio.titulo}' foi registrada.\n"
                f"Boa sorte!"
            )
        else:
            await interaction.followup.send(
                f"🔄 **Submissão atualizada!**\n"
                f"Seu novo link para o desafio '{desafio.titulo}' foi salvo."
            )

    except Exception as e:
        print(f"Erro ao salvar submissão: {e}")
        await interaction.followup.send(f"❌ Ocorreu um erro inesperado ao salvar sua submissão. Tente novamente. {e}")

## INICIAR VOTAÇÃO ##

@tree.command(
    name="iniciar-votacao",
    description="Fecha as submissões de um desafio e inicia a votação.",
    guild=TEST_GUILD
)

@app_commands.describe(id_desafio="O ID do desafio para abrir a votação.")
@app_commands.checks.has_permissions(administrator=True)
async def iniciar_votacao(interaction: discord.Interaction, id_desafio: int):
    await interaction.response.defer(ephemeral=True)

    canal_votacao = client.get_channel(int(os.getenv("DISCORD_VOTE_CHANNEL_ID")))
    if not canal_votacao:
        await interaction.followup.send(f"❌ Erro: Não encontrei o canal de votação. Verifique o ID.")
        return

    try:
        desafio = await Desafio.get(id=id_desafio).prefetch_related('submissoes__usuario')

    except Exception:
        await interaction.followup.send(f"❌ Erro: Desafio com ID {id_desafio} não encontrado.")
        return

    if desafio.status != Desafio.Status.ABERTO:
        await interaction.followup.send(f"❌ Erro: Este desafio não está 'ABERTO'. Status atual: {desafio.status}.")
        return
        
    if not desafio.submissoes:
         await interaction.followup.send(f"❌ Erro: Este desafio não tem nenhuma submissão para votar.")
         return

    
    desafio.status = Desafio.Status.VOTACAO
    await desafio.save()
    
    await canal_votacao.send(f"--- 🗳️ VOTAÇÃO INICIADA: {desafio.titulo} 🗳️ ---")
    
    total_submissoes = len(desafio.submissoes)
    await interaction.followup.send(f"✅ Votação iniciada! Postando {total_submissoes} submissões em {canal_votacao.mention}...")

    
    for submissao in desafio.submissoes:
        
        username = submissao.usuario.username

        embed = discord.Embed(
            title=f"Solução de: {username}",
            description=f"Link para o código: {submissao.link_codigo}",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"ID da Submissão: {submissao.id}")

        msg = await canal_votacao.send(embed=embed)
        await msg.add_reaction("🌟")

        submissao.mensagem_votacao_id = msg.id
        await submissao.save()

    await canal_votacao.send(f"--- 🏁 Fim das submissões 🏁 ---")

## EVENTOS DE REAÇÕES PARA VOTAÇÃO ##

@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if str(payload.emoji) != "🌟" or payload.user_id == client.user.id:
        return

    if payload.channel_id != int(os.getenv("DISCORD_VOTE_CHANNEL_ID")): 
        return

    try:
        submissao = await Submissao.get(mensagem_votacao_id=payload.message_id)
        
        usuario_votante, _ = await Usuario.get_or_create(
            discord_id=payload.user_id,
            defaults={"username": payload.member.name if payload.member else "Usuário Desconhecido"}
        )

        voto, foi_criado = await Voto.get_or_create(
            submissao=submissao,
            usuario=usuario_votante,
            tipo_voto="comunidade",
            defaults={"mensagem_id": payload.message_id} 
        )

        if foi_criado:
            submissao.pontos_comunidade += PONTOS_POR_VOTO_COMUNIDADE
            submissao.pontos_total += PONTOS_POR_VOTO_COMUNIDADE
            await submissao.save()
        else:
            return
        
    except Exception as e:
        print(f"[ERRO] Erro em on_raw_reaction_add: {e}")

@client.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if str(payload.emoji) != "🌟" or payload.user_id == client.user.id:
        return

    if payload.channel_id != int(os.getenv("DISCORD_VOTE_CHANNEL_ID")):
        return

    try:
        voto_removido = await Voto.get(
            usuario_id=payload.user_id,
            mensagem_id=payload.message_id,
            tipo_voto="comunidade"
        ).prefetch_related('submissao')

        submissao = voto_removido.submissao
        submissao.pontos_comunidade -= PONTOS_POR_VOTO_COMUNIDADE
        submissao.pontos_total -= PONTOS_POR_VOTO_COMUNIDADE
        
        if submissao.pontos_comunidade < 0:
            submissao.pontos_comunidade = 0
        if submissao.pontos_total < 0 and submissao.pontos_jurados == 0 and submissao.pontos_ia == 0:
             submissao.pontos_total = 0 
            
        await submissao.save()
        await voto_removido.delete()
        
        print(f"[SUCESSO] Voto removido para submissão {submissao.id}. Novos pontos: {submissao.pontos_total}")

    except Exception as e:
        print(f"[AVISO] Erro ao remover voto (provavelmente não existia ou já foi removido): {e}")

## INICIAR VOTAÇÃO POR JURADO ##

@tree.command(
    name="votar-jurado",
    description="Registra o voto de um jurado em uma submissão.",
    guild=TEST_GUILD
)
@app_commands.describe(id_submissao="O ID da submissão (veja no canal #votacao)")
@app_commands.checks.has_role(NOME_CARGO_JURADO) 
async def votar_jurado(interaction: discord.Interaction, id_submissao: int):
    await interaction.response.defer(ephemeral=True)

    try:
        submissao = await Submissao.get(id=id_submissao).prefetch_related('desafio', 'usuario')
    except Exception:
        await interaction.followup.send(f"❌ Erro: Submissão com ID {id_submissao} não encontrada.")
        return

    if submissao.desafio.status != Desafio.Status.VOTACAO:
        await interaction.followup.send(f"❌ Erro: Este desafio não está em votação (Status: {submissao.desafio.status}).")
        return

    if submissao.usuario.discord_id == interaction.user.id:
        await interaction.followup.send("❌ Erro: Você não pode votar na sua própria submissão.")
        return
        
    jurado_db, _ = await Usuario.get_or_create(
        discord_id=interaction.user.id,
        defaults={"username": interaction.user.name}
    )

    
    try:
        voto, criado = await Voto.get_or_create(
            submissao=submissao,
            usuario=jurado_db,
            tipo_voto="jurado" 
        )

        if not criado:
            await interaction.followup.send("⚠️ Você já votou nesta submissão como jurado.")
            return

        submissao.pontos_jurados += PONTOS_POR_VOTO_JURADO
        submissao.pontos_total += PONTOS_POR_VOTO_JURADO
        await submissao.save()

        await interaction.followup.send(f"✅ Voto de jurado computado! (+{PONTOS_POR_VOTO_JURADO} pontos para a submissão {submissao.id}).")

    except Exception as e:
        print(f"Erro ao salvar voto de jurado: {e}")
        await interaction.followup.send(f"❌ Ocorreu um erro ao salvar seu voto: {e}")


@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "Você não tem permissão (Admin) para usar este comando.",
            ephemeral=True
        )
    elif isinstance(error, app_commands.MissingRole):
        await interaction.response.send_message(
            f"Você precisa do cargo '{NOME_CARGO_JURADO}' para usar este comando.",
            ephemeral=True
        )
    else:
        print(error)
        if interaction.response.is_done():
            await interaction.followup.send(f"Ocorreu um erro: {error}", ephemeral=True)
        else:
            await interaction.response.send_message(f"Ocorreu um erro: {error}", ephemeral=True)

## Encerra votação ##

@tree.command(
    name="encerrar-votacao",
    description="Fecha a votação de um desafio e anuncia os vencedores.",
    guild=TEST_GUILD
)
@app_commands.describe(id_desafio="O ID do desafio para fechar.")
@app_commands.checks.has_permissions(administrator=True)
async def encerrar_votacao(interaction: discord.Interaction, id_desafio: int):
    await interaction.response.defer(ephemeral=True)

    try:
        desafio = await Desafio.get(id=id_desafio)
    except Exception:
        await interaction.followup.send(f"❌ Erro: Desafio com ID {id_desafio} não encontrado.")
        return

    if desafio.status != Desafio.Status.VOTACAO:
        await interaction.followup.send(f"❌ Erro: Este desafio não está em 'VOTAÇÃO'. Status atual: {desafio.status}.")
        return

    desafio.status = Desafio.Status.FECHADO
    await desafio.save()

    submissoes_vencedoras = await Submissao.filter(desafio=desafio).order_by(
        '-pontos_total'
    ).prefetch_related('usuario') 

    if not submissoes_vencedoras:
        await interaction.followup.send(f"✅ Desafio {desafio.titulo} fechado. Não houveram submissões.")
        return

    
    for sub in submissoes_vencedoras:
        usuario = sub.usuario
        usuario.pontos_total += sub.pontos_total
        await usuario.save()

    
    canal_anuncios = client.get_channel(int(os.getenv("DISCORD_CHANNEL_ID"))) 

    embed = discord.Embed(
        title=f"🏆 Votação Encerrada: {desafio.titulo} 🏆",
        description=f"A votação para o Nível '{desafio.nivel.value}' está completa! Obrigado a todos que participaram.",
        color=discord.Color.green()
    )

    
    ranking_descricao = ""
    medalhas = ["🥇", "🥈", "🥉"]

    for i, sub in enumerate(submissoes_vencedoras[:3]):
        medalha = medalhas[i] if i < len(medalhas) else f"**{i+1}.**"
        ranking_descricao += (
            f"{medalha} {sub.usuario.username} com **{sub.pontos_total} pontos**\n"
            f"(Comunidade: {sub.pontos_comunidade}, Jurados: {sub.pontos_jurados}, IA: {sub.pontos_ia})\n\n"
        )
    
    if not ranking_descricao:
        ranking_descricao = "Nenhuma submissão recebeu pontos."

    embed.add_field(name="Resultados Finais", value=ranking_descricao, inline=False)
    embed.set_footer(text="Parabéns aos vencedores! 🎉")

    if canal_anuncios:
        await canal_anuncios.send(content="@everyone Confira os resultados!", embed=embed)
        await interaction.followup.send(f"✅ Desafio fechado e vencedores anunciados em {canal_anuncios.mention}!")
    else:
        await interaction.followup.send("✅ Desafio fechado. (Não consegui anunciar no canal, verifique o ID).")

##

##

@tree.command(
    name="ranking",
    description="Mostra o ranking geral de pontos da comunidade.",
    guild=TEST_GUILD
)
async def ranking(interaction: discord.Interaction):
    await interaction.response.defer()

    top_usuarios = await Usuario.all().order_by('-pontos_total').limit(10)

    if not top_usuarios:
        await interaction.followup.send("Ainda não há ninguém no ranking. Participe de um desafio!")
        return

    
    embed = discord.Embed(
        title="🏆 Ranking Geral da Comunidade 🏆",
        description="Pontuação acumulada de todos os desafios.",
        color=discord.Color.purple()
    )

    ranking_descricao = ""
    medalhas = ["🥇", "🥈", "🥉"]

    for i, usuario in enumerate(top_usuarios):
        if usuario.pontos_total == 0: continue 

        prefixo = medalhas[i] if i < len(medalhas) else f"**{i+1}.**"
        ranking_descricao += f"{prefixo} {usuario.username} **{usuario.pontos_total} pontos**\n"

    if not ranking_descricao:
         ranking_descricao = "Ninguém pontuou ainda."

    embed.add_field(name="Top 10 Desenvolvedores", value=ranking_descricao)
    await interaction.followup.send(embed=embed)

## FIM DOS COMANDOS ##

client.run(TOKEN)