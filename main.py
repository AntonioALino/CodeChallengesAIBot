import discord
import os
import datetime
from discord.ext import tasks
from discord import app_commands
from discord.app_commands import Choice
from dotenv import load_dotenv
from tortoise.functions import Sum


from ai_integration import fetch_code_from_url, generate_ai_challenge, get_ai_score
from database import Submissao, Usuario, Voto, init_db, close_db, Desafio 

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
PONTOS_POR_VOTO_COMUNIDADE = 15
PONTOS_POR_VOTO_JURADO = 30

NOME_CARGO_JURADO = "Jurado"

CHALLENGE_CONFIG = {
        "iniciante": {
            "role_id": int(os.getenv("ROLE_ID_INICIANTE")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_INICIANTE"))
        },
        "junior": {
            "role_id": int(os.getenv("ROLE_ID_JUNIOR")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_JUNIOR"))
        },
        "pleno": {
            "role_id": int(os.getenv("ROLE_ID_PLENO")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_PLENO")),
        },
        "senior": {
            "role_id": int(os.getenv("ROLE_ID_SENIOR")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_SENIOR")),
        }
    }

ultimo_dia_checado = None
ultima_semana_checada = None
ultimo_mes_checado = None

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
    Choice(name='Iniciante', value='iniciante'),
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

    CHALLENGE_CONFIG = {
        "iniciante": {
            "role_id": int(os.getenv("ROLE_ID_INICIANTE")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_INICIANTE"))
        },
        "junior": {
            "role_id": int(os.getenv("ROLE_ID_JUNIOR")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_JUNIOR"))
        },
        "pleno": {
            "role_id": int(os.getenv("ROLE_ID_PLENO")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_PLENO")),
        },
        "senior": {
            "role_id": int(os.getenv("ROLE_ID_SENIOR")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_SENIOR")),
        }
    }

    nivel_key = nivel.value 
    config = CHALLENGE_CONFIG.get(nivel_key)

    if not config:
        await interaction.followup.send(f"⚠️ Desafio criado no DB (ID: {novo_desafio.id}), mas NENHUM canal/role foi configurado no CHALLENGE_CONFIG para o nível '{nivel_key}'.")
        return

    try:
        canal_desafio = client.get_channel(config["channel_id"])
        role_mention = f"<@&{config['role_id']}>"
        
        if canal_desafio:
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

            await canal_desafio.send(content=f"{role_mention}, novo desafio disponível!", embed=embed)
            
            await interaction.followup.send(f"✅ Desafio '{titulo}' (ID: {novo_desafio.id}) criado com sucesso e anunciado em {canal_desafio.mention}!")
        
        else:
            await interaction.followup.send(f"⚠️ Desafio criado no DB (ID: {novo_desafio.id}), mas não encontrei o canal com ID {config['channel_id']}. Verifique o CHALLENGE_CONFIG.")

    except Exception as e:
        print(f"Erro ao anunciar desafio: {e}")
        await interaction.followup.send(f"⚠️ Desafio criado no DB (ID: {novo_desafio.id}), mas falhei ao tentar anunciá-lo. Erro: {e}")

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

        submissoes_vencedoras = sorted(submissao, key=lambda s: s.pontos_total, reverse=True)

        for sub in submissoes_vencedoras:
            usuario = sub.usuario
            
            pontos_ganhos = sub.pontos_total 
            
            usuario.pontos_total += pontos_ganhos
            usuario.pontos_mes += pontos_ganhos
            usuario.pontos_semana += pontos_ganhos
            
            await usuario.save()

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

    submissoes = await Submissao.filter(desafio=desafio).prefetch_related('usuario')

    if not submissoes:
        await interaction.followup.send(f"✅ Desafio {desafio.titulo} fechado. Não houveram submissões.")
        return

    await interaction.edit_original_response(content=f"Votação encerrada. Iniciando análise da IA para {len(submissoes)} submissões...")
    
    ## IA ##

    justificativas_ia = {} 

    for sub in submissoes:
        await interaction.edit_original_response(content=f"Analisando submissão {sub.id} de {sub.usuario.username}...")
        
        code_text = await fetch_code_from_url(sub.link_codigo)
        
        if not code_text:
            print(f"Não foi possível buscar o código da submissão {sub.id} (Link: {sub.link_codigo})")
            justificativas_ia[sub.id] = "Erro ao buscar o código do link."
            continue 

        nota, justificativa = await get_ai_score(code_text, desafio.descricao)
        
        sub.pontos_ia = nota
        sub.pontos_total += nota
        await sub.save()
        
        justificativas_ia[sub.id] = justificativa 
        
    await interaction.edit_original_response(content="Análise da IA completa! Calculando rankings...")

    ## IA ##

    submissoes_vencedoras = sorted(submissoes, key=lambda s: s.pontos_total, reverse=True)

    for sub in submissoes_vencedoras:
        usuario = sub.usuario
        
        pontos_ganhos = sub.pontos_total 
        
        usuario.pontos_total += pontos_ganhos
        usuario.pontos_mes += pontos_ganhos
        usuario.pontos_semana += pontos_ganhos
        
        await usuario.save()

    
    challenge_level = desafio.nivel.value 
    config = CHALLENGE_CONFIG.get(challenge_level) 

    canal_anuncios = int(os.getenv("DISCORD_CHANNEL_WINNER_ANNOUNCEMENT_ID"))
    
    if config:
        canal_anuncios = client.get_channel(config["channel_id"])
    
    if not canal_anuncios:
        await interaction.followup.send(f"✅ Desafio fechado. (AVISO: Não encontrei o canal de anúncio para o nível '{challenge_level}' no CHALLENGE_CONFIG).")
        return 

    embed = discord.Embed(
        title=f"🏆 Votação Encerrada: {desafio.titulo} 🏆",
        description=f"A votação para o Nível '{desafio.nivel.value}' está completa! Obrigado a todos que participaram.",
        color=discord.Color.green()
    )

    medalhas = ["🥇 1º Lugar", "🥈 2º Lugar", "🥉 3º Lugar"]

    if not submissoes_vencedoras:
        embed.add_field(name="Resultados Finais", value="Nenhuma submissão recebeu pontos.")
    else:
        for i, sub in enumerate(submissoes_vencedoras[:3]):
            
            field_name = medalhas[i] if i < len(medalhas) else f"**{i+1}º Lugar**"
            
            feedback_ia = justificativas_ia.get(sub.id, 'N/A')
            if len(feedback_ia) > 500:
                feedback_ia = feedback_ia[:500] + "..."

            field_value = (
                f"**Participante:** {sub.usuario.username}\n"
                f"**Pontos Totais:** **{sub.pontos_total}**\n"
                f"*(Comunidade: {sub.pontos_comunidade}, Jurados: {sub.pontos_jurados}, IA: {sub.pontos_ia})*\n"
                f"**Feedback da IA:** *{feedback_ia}*\n"
            )
            
            embed.add_field(name=field_name, value=field_value, inline=False)

    embed.set_footer(text="Parabéns aos vencedores! 🎉")

    role_mention = f"<@&{config['role_id']}>"
    await canal_anuncios.send(content=f"{role_mention} Confira os resultados!", embed=embed)
    await interaction.followup.send(f"✅ Desafio fechado e vencedores anunciados em {canal_anuncios.mention}!")

## FEAT DE RANKING GERAL ##

@tree.command(
    name="ranking",
    description="Mostra o ranking de pontos da comunidade.",
    guild=TEST_GUILD
)
@app_commands.describe(
    periodo="O tipo de ranking que você quer ver (padrão: Semanal)."
)
@app_commands.choices(periodo=[
    Choice(name='Semanal (Esta Semana)', value='semana'),
    Choice(name='Mensal (Este Mês)', value='mes'),
    Choice(name='Geral (Todos os Tempos)', value='geral'),
])
async def ranking(
    interaction: discord.Interaction, 
    periodo: Choice[str] = None 
):
    await interaction.response.defer()

    tipo_ranking = 'semana'
    if periodo:
        tipo_ranking = periodo.value

    hoje = datetime.datetime.now() 
    top_usuarios = []
    titulo_ranking = ""
    campo_pontos = "" 

    if tipo_ranking == 'semana':
        titulo_ranking = f"🏆 Ranking Semanal 🏆"
        campo_pontos = 'pontos_semana'
        
    elif tipo_ranking == 'mes':
        titulo_ranking = f"🏆 Ranking Mensal ({hoje.strftime('%B de %Y')}) 🏆"
        campo_pontos = 'pontos_mes'

    else: 
        titulo_ranking = "🏆 Ranking Geral (Todos os Tempos) 🏆"
        campo_pontos = 'pontos_total'
        
    top_usuarios = await Usuario.all().order_by(f'-{campo_pontos}').limit(10)


    pontos_do_primeiro = 0
    if top_usuarios:
        pontos_do_primeiro = getattr(top_usuarios[0], campo_pontos) or 0 

    if not top_usuarios or pontos_do_primeiro == 0:
        embed = discord.Embed(
            title=titulo_ranking,
            description="👻 Parece que está tudo zerado por aqui.\nNinguém pontuou ainda neste período.",
            color=discord.Color.light_grey()
        )
        await interaction.followup.send(embed=embed)
        return

    embed = discord.Embed(
        title=titulo_ranking,
        description="Pontuação acumulada dos desafios.",
        color=discord.Color.purple()
    )

    ranking_descricao = ""
    medalhas = ["🥇", "🥈", "🥉"]

    for i, usuario in enumerate(top_usuarios):
        pontos = getattr(usuario, campo_pontos) or 0
        
        prefixo = medalhas[i] if i < len(medalhas) else f"**{i+1}.**"
        ranking_descricao += f"{prefixo} {usuario.username} - **{pontos} pontos**\n"

    embed.add_field(name="Top 10 Desenvolvedores", value=ranking_descricao)
    await interaction.followup.send(embed=embed)

##

## FEAT DE GERAR DESAFIOS COM IA ##

@tree.command(
    name="gerar-desafio-ia",
    description="Gera um novo desafio de programação usando IA.",
    guild=TEST_GUILD
)
@app_commands.describe(
    tema="O tema central do desafio (ex: 'API REST', 'Algoritmo de Ordenação')",
    nivel="O nível de dificuldade do desafio",
    dias_para_concluir="Quantos dias os membros terão para submeter (ex: 7)"
)
@app_commands.choices(nivel=[
    Choice(name='Júnior', value='junior'),
    Choice(name='Pleno', value='pleno'),
    Choice(name='Sênior', value='senior'),
])
@app_commands.checks.has_permissions(administrator=True)
async def gerar_desafio_ia(
    interaction: discord.Interaction,
    tema: str,
    nivel: Choice[str],
    dias_para_concluir: int
):
    await interaction.response.defer(ephemeral=True) 
    
    titulo, descricao = await generate_ai_challenge(nivel.value, tema)
    
    if not titulo or not descricao:
        await interaction.followup.send(f"❌ Erro ao gerar desafio com IA: {descricao}")
        return

    
    data_fim = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=dias_para_concluir)

    try:
        novo_desafio = await Desafio.create(
            titulo=titulo,
            descricao=descricao,
            nivel=nivel.value,
            data_fim_submissao=data_fim
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Erro ao salvar o desafio da IA no banco de dados: {e}")
        return


    CHALLENGE_CONFIG = {
        "iniciante": {
            "role_id": int(os.getenv("ROLE_ID_INICIANTE")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_INICIANTE"))
        },
        "junior": {
            "role_id": int(os.getenv("ROLE_ID_JUNIOR")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_JUNIOR"))
        },
        "pleno": {
            "role_id": int(os.getenv("ROLE_ID_PLENO")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_PLENO")),
        },
        "senior": {
            "role_id": int(os.getenv("ROLE_ID_SENIOR")),
            "channel_id": int(os.getenv("DISCORD_CHANNEL_SENIOR")),
        }
    }

    nivel_key = nivel.value 
    config = CHALLENGE_CONFIG.get(nivel_key)

    if not config:
        await interaction.followup.send(f"⚠️ Desafio criado no DB (ID: {novo_desafio.id}), mas NENHUM canal/role foi configurado no CHALLENGE_CONFIG para o nível '{nivel_key}'.")
        return

    try:
        canal_desafio = client.get_channel(config["channel_id"])
        role_mention = f"<@&{config['role_id']}>"
        
        if canal_desafio:
            embed = discord.Embed(
                title=f"🚀 Novo Desafio: {titulo} (Nível: {nivel.name})",
                description=descricao,
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Prazo de Submissão",
                value=f"Até <t:{int(data_fim.timestamp())}:F>"
            )
            embed.set_footer(text=f"ID do Desafio: {novo_desafio.id} | Use /submeter para participar!")

            await canal_desafio.send(content=f"{role_mention}, novo desafio disponível!", embed=embed)
            
            await interaction.followup.send(f"✅ Desafio '{titulo}' (ID: {novo_desafio.id}) criado com sucesso e anunciado em {canal_desafio.mention}!")
        
        else:
            await interaction.followup.send(f"⚠️ Desafio criado no DB (ID: {novo_desafio.id}), mas não encontrei o canal com ID {config['channel_id']}. Verifique o CHALLENGE_CONFIG.")

    except Exception as e:
        print(f"Erro ao anunciar desafio: {e}")
        await interaction.followup.send(f"⚠️ Desafio criado no DB (ID: {novo_desafio.id}), mas falhei ao tentar anunciá-lo. Erro: {e}")

## FIM DOS COMANDOS ##

client.run(TOKEN)