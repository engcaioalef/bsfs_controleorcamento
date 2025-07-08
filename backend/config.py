import os

# Obtém o caminho absoluto do diretório onde este arquivo está.
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    """
    Configurações da aplicação Flask.
    """
    # Chave secreta gerada para proteger sessões e cookies.
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'd9a8f7c6e5b4a3c2d1e0f9b8a7c6d5e4f3a2b1c0d9e8f7a6'

    # String de conexão com o banco de dados.
    # A senha foi atualizada conforme solicitado.
    # Formato: postgresql://[usuario]:[senha]@[host]:[porta]/[nome_do_banco]
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:TI$DBA-985643@localhost:5432/orcamento_db'

    # Desativa um recurso do SQLAlchemy que não usaremos e que emite avisos.
    SQLALCHEMY_TRACK_MODIFICATIONS = False
