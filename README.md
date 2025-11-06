# 🤖 CodeChallengeBot

Um bot para Discord focado em gerenciar desafios de programação (Code Challenges) semanais, com um sistema de votação e ranking para comunidades de desenvolvedores.

Este bot foi projetado para automatizar todo o ciclo de vida de um desafio: desde o lançamento, passando pela coleta de submissões, até a votação (comunitária e de jurados) e a declaração de vencedores.

## ✨ Funcionalidades Principais

* **Criação de Desafios:** Admins podem lançar novos desafios com níveis de dificuldade (Júnior, Pleno, Sênior) e prazos definidos.
* **Sistema de Submissão:** Usuários podem submeter suas soluções através de um simples comando, enviando um link (GitHub, Gist, etc.).
* **Votação Híbrida:**
    * **Votação da Comunidade:** Membros votam usando reações (⭐) em um canal dedicado.
    * **Votação de Jurados:** Membros com o cargo `Jurado` podem usar um comando especial para dar um voto com peso maior.
* **Ranking Automático:** O bot calcula os pontos de cada submissão (comunidade + jurados) e atualiza um ranking geral persistente.
* **Gerenciamento de Status:** O bot controla o status de um desafio (Aberto, Votação, Fechado).

## 🔧 Stack de Tecnologia

* **Linguagem:** Python 3.10+
* **Biblioteca Discord:** [discord.py](https://discordpy.readthedocs.io/en/stable/) (com `app_commands`)
* **Banco de Dados:** PostgreSQL
* **ORM:** [Tortoise ORM](https://tortoise.github.io/) (para interação assíncrona com o DB)
* **Driver do DB:** `asyncpg`
* **Variáveis de Ambiente:** `python-dotenv`

---

## 🚀 Instalação e Configuração

Siga estes passos para rodar sua própria instância do bot.

### 1. Pré-requisitos

* Python 3.10 ou superior
* Uma conta no Discord com um servidor onde você tenha permissões de Admin.
* Um banco de dados PostgreSQL acessível (localmente ou na nuvem, como [Supabase](https://supabase.com/) ou [Railway](https://railway.app/)).

### 2. Configuração do Bot no Discord

1.  Acesse o [Portal de Desenvolvedores do Discord](https://discord.com/developers/applications).
2.  Crie uma "New Application".
3.  Vá para a aba **"Bot"** e clique em "Add Bot".
4.  **Obtenha o Token:** Clique em "Reset Token" e copie o token. **(Guarde isso para o `.env`)**.
5.  **Ative as Privileged Intents:** Na mesma página, ative:
    * `SERVER MEMBERS INTENT`
    * `MESSAGE CONTENT INTENT`
6.  **Convide o Bot:**
    * Vá para a aba "OAuth2" > "URL Generator".
    * Marque os scopes `bot` e `applications.commands`.
    * Dê as permissões de Bot necessárias (como "Send Messages", "Read Message History", "Add Reactions").
    * Copie a URL gerada, cole no seu navegador e adicione o bot ao seu servidor.

### 3. Configuração do Projeto Local

1.  Clone este repositório:
    ```bash
    git clone [https://github.com/seu-usuario/seu-repositorio.git](https://github.com/seu-usuario/seu-repositorio.git)
    cd seu-repositorio
    ```

2.  Crie e ative um ambiente virtual (venv):
    ```bash
    python -m venv venv
    source venv/bin/activate  # No Windows: venv\Scripts\activate
    ```

3.  Instale as dependências:
    ```bash
    pip install discord.py tortoise-orm asyncpg python-dotenv
    ```
    *(Recomendado: crie um `requirements.txt` com `pip freeze > requirements.txt`)*

4.  Configure suas variáveis de ambiente. Crie um arquivo chamado `.env` na raiz do projeto e preencha-o com base no modelo abaixo:

    **Arquivo `.env`:**
    ```env
    # Token do Bot (do Portal de Dev do Discord)
    DISCORD_TOKEN=SEU_TOKEN_AQUI
    DISCORD_SERVER_ID=SEU_SERVER_ID
    DISCORD_CHANNEL_ID=SEU_CHANNEL_ID
    DISCORD_VOTE_CHANNEL_ID=SEU_VOTE_CHANNEL_ID
    
    # Credenciais do seu banco de dados PostgreSQL
    DB_HOST=seu_host_aqui
    DB_PORT=5432
    DB_USER=seu_usuario_aqui
    DB_PASS=sua_senha_aqui
    DB_NAME=seu_banco_aqui
    ```

### 4. Configuração do Servidor Discord

Antes de rodar o bot, você precisa configurar seu servidor:

1.  **Cargos:** Crie um cargo chamado exatamente `Jurado`.
2.  **Canais:**
    * Crie um canal para anúncios de desafios (ex: `#desafios`).
    * Crie um canal para votações (ex: `#votacao`).
3.  **Obtenha os IDs:**
    * Ative o "Modo de Desenvolvedor" nas suas Configurações de Usuário > Avançado.
    * Clique com o botão direito no seu servidor, nos canais e pegue seus IDs.

4.  **Atualize o `main.py`:**
    Você **precisa** atualizar as seguintes variáveis no topo do arquivo `main.py` com os IDs que você copiou:

    ```python
    TEST_GUILD = discord.Object(id=SEU_ID_DE_SERVIDOR_AQUI)
    ID_DO_CANAL_DESAFIOS = ID_DO_CANAL_DE_DESAFIOS_AQUI
    ID_DO_CANAL_VOTACAO = ID_DO_CANAL_DE_VOTACAO_AQUI
    ```

### 5. Rodando o Bot

Após tudo configurado, inicie o bot:

```bash
python main.py
