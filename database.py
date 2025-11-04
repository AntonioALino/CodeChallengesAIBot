import os
from dotenv import load_dotenv
from enum import Enum
from tortoise import Tortoise, run_async, fields
from tortoise.models import Model

load_dotenv()

class User(Model):
    discord_id = fields.BigIntField(pk=True)
    username = fields.CharField(max_length=100)
    pontos_total = fields.IntField(default=0)

    def __str__(self):
        return self.username
    
class Desafio(Model):
    class Nivel(str, Enum):
        JUNIOR = "junior"
        PLENO = "pleno"
        SENIOR = "senior"

    class Status(str, Enum):
        ABERTO = "aberto"
        VOTACAO = "votacao"
        FECHADO = "fechado"

    id = fields.IntField(pk=True) 
    titulo = fields.CharField(max_length=255)
    descricao = fields.TextField()
    nivel = fields.CharEnumField(Nivel, max_length=10, default=Nivel.JUNIOR)
    status = fields.CharEnumField(Status, max_length=10, default=Status.ABERTO)
    data_inicio = fields.DatetimeField(auto_now_add=True) # auto_now_add é o 'default=now()'
    data_fim_submissao = fields.DatetimeField()

    def __str__(self):
        return self.titulo
    
DB_CONFIG = {
    'connections': {
        'default': {
            'engine': 'tortoise.backends.asyncpg',
            'credentials': {
                'host': os.getenv('DB_HOST'),
                'port': os.getenv('DB_PORT', 5432),
                'user': os.getenv('DB_USER'),
                'password': os.getenv('DB_PASS'),
                'database': os.getenv('DB_NAME'),
            },
        }
    },
    'apps': {
        'models': {
            'models': [__name__], 
            'default_connection': 'default',
        }
    }
}

async def init_db():
    print("Inicializando Tortoise...")
    await Tortoise.init(config=DB_CONFIG)
    
    await Tortoise.generate_schemas()
    print("Banco de dados conectado e schemas gerados.")

async def close_db():
    await Tortoise.close_connections()