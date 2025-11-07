import os
import aiohttp
import json

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL_CHALLENGE = os.getenv("OLLAMA_MODEL_CHALLENGE", "llama3:8b")
OLLAMA_MODEL_ANALYSIS = os.getenv("OLLAMA_MODEL_ANALYSIS", "codellama:7b")
OLLAMA_API_ENDPOINT = f"{OLLAMA_HOST}/api/generate"

## FEAT PARA CHAMAR O OLLAMA ##

async def _call_ollama(model_name: str, prompt: str, expect_json: bool = True):
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }

    if expect_json:
        payload["format"] = "json"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OLLAMA_API_ENDPOINT, json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    print(f"Erro do Ollama (Status {response.status}): {error_text}")
                    return None, f"Erro do servidor Ollama: {error_text}"
                
                data = await response.json()

                response_content = data.get('response')

                if not response_content:
                    return None, "Ollama retornou uma resposta vazia."
                
                return response_content, None
            
    except aiohttp.ClientConnectorError:
        return None, "Erro de Conexão: Não foi possível se conectar ao servidor Ollama. Ele está rodando?"
    except aiohttp.ClientTimeout:
        return None, "Erro de Timeout: A IA demorou muito para responder."
    except Exception as e:
        print(f"Erro desconhecido ao chamar Ollama: {e}")
        return None, f"Erro inesperado: {e}"  
    
## FEAT DE GERAR DESAFIOS ##

async def generate_ai_challenge(nivel : str, tema: str):

    
    prompt = f"""
    Você é um Coordenador de Desafios de Programação.
    Gere um desafio para o nível '{nivel}' com o tema '{tema}'.
    
    Sua resposta DEVE ser um objeto JSON, e nada mais.
    O JSON deve ter duas chaves: "titulo" e "descricao".
    
    - 'titulo': Um título criativo e curto (máx 50 caracteres).
    - 'descricao': Uma descrição clara do desafio. Use quebras de linha (\\n) para formatar a descrição.
    """

    json_str, error = await _call_ollama(OLLAMA_MODEL_CHALLENGE, prompt, expect_json=True)

    if error:
        return None, error
        
    try:
        json_text = json_str.strip().replace('```json', '').replace('```', '')

        if not json_text:
             print("[ERRO] A IA retornou um JSON vazio.")
             return None, "A IA retornou uma resposta vazia após a limpeza."
        
        data = json.loads(json_text)
        titulo = data.get('titulo')
        descricao = data.get('descricao')


        return titulo, descricao
        
    except json.JSONDecodeError:
        print(f"Erro de JSON da IA (geração): A IA não retornou um JSON válido. Resposta: {json_str}")
        return None, "A IA retornou um formato de texto inválido."
    except Exception as e:
        print(f"Erro ao processar desafio da IA: {e}")
        return None, f"Erro: {e}"
    
## FEAT DE ANALISAR SOLUÇÕES ##

async def fetch_code_from_url(url: str) -> str:
    if 'pastebin.com' in url and '/raw/' not in url:
        if url.endswith('/'):
            url = url[:-1]
        url = url.replace('pastebin.com/', 'pastebin.com/raw/')

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    print(f"Erro ao buscar código: Status {resp.status}")
                    return None
    except Exception as e:
        print(f"Erro de rede ao buscar código: {e}")
        return None

async def get_ai_score(code_text: str, challenge_description: str):

    prompt = f"""
    Você é um Juiz Sênior de um desafio de programação.
    O desafio era: "{challenge_description}"
    
    O código submetido é:
    ```
    {code_text}
    ```
    
    Analise o código com base em:
    1. Correção (atinge o objetivo?)
    2. Eficiência
    3. Legibilidade
    
    Responda APENAS com um objeto JSON com duas chaves:
    1. "nota": Um número inteiro de 0 a 5.
    2. "justificativa": Um parágrafo curto (máx 3-4 frases) explicando a nota.
    """
    
    json_str, error = await _call_ollama(OLLAMA_MODEL_ANALYSIS, prompt, expect_json=True)
    
    if error:
        return 0, error
        
    try:
        json_text = json_str.strip().replace('```json', '').replace('```', '')
        data = json.loads(json_text)
        return data.get('nota', 0), data.get('justificativa', 'Nenhuma justificativa fornecida.')
        
    except json.JSONDecodeError:
        print(f"Erro de JSON da IA (análise): A IA não retornou um JSON válido. Resposta: {json_str}")
        return 0, "A IA retornou um formato de texto inválido."
    except Exception as e:
        print(f"Erro ao processar análise da IA: {e}")
        return 0, f"Erro: {e}"