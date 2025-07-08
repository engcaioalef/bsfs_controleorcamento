import psycopg2
import psycopg2.extras
import pandas as pd
import os
import re
import csv
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from config import Config
from datetime import datetime
from dateutil.relativedelta import relativedelta
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)

# Configuração da pasta de uploads
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


# --- FUNÇÃO AUXILIAR CORRIGIDA ---
def limpar_e_converter_moeda(valor_str):
    """
    Função para converter valores monetários do formato brasileiro para float,
    tratando None, NaN e strings vazias.
    """
    if valor_str is None or pd.isna(valor_str):
        return 0.0
    # Converte para string e remove espaços
    s = str(valor_str).strip()
    if not s:
        return 0.0
    # Remove 'R$' e outros caracteres não numéricos, exceto '.' e ',' e '-' (para negativos)
    s = re.sub(r'[^\d,.-]', '', s)
    # Remove pontos de milhar
    s = s.replace('.', '')
    # Troca vírgula decimal por ponto
    s = s.replace(',', '.')
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0

# --- DECORATORS PARA CONTROLE DE ACESSO ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'message': 'Autenticação necessária.'}), 401
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    def wrapper(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get('papel') not in roles:
                return jsonify({'message': 'Acesso não autorizado para esta função.'}), 403
            return f(*args, **kwargs)
        return wrapper
    return wrapper

# --- FUNÇÕES DE BANCO DE DADOS ---
def get_db_connection():
    conn = psycopg2.connect(app.config['SQLALCHEMY_DATABASE_URI'])
    return conn

# --- ROTAS DE AUTENTICAÇÃO E DASHBOARD ---
@app.route("/")
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route("/api/login", methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    query = "SELECT u.*, s.nome as setor_nome, p.nome as papel_nome FROM usuarios u LEFT JOIN setores s ON u.setor_id = s.id LEFT JOIN papeis p ON u.papel_id = p.id WHERE u.email = %s"
    cursor.execute(query, (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    if not user or not check_password_hash(user['hash_senha'], password):
        return jsonify({'message': 'E-mail ou senha inválidos.'}), 401
    session.clear()
    session.update({
        'user_id': user['id'],
        'user_name': user['nome_completo'],
        'user_setor': user['setor_nome'],
        'user_setor_id': user['setor_id'],
        'papel': user['papel_nome'],
        'primeiro_login': user['primeiro_login']
    })
    return jsonify({'message': 'Login bem-sucedido!'}), 200

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route("/dashboard")
@login_required
def dashboard():
    if session.get('primeiro_login'):
        return redirect(url_for('trocar_senha_page'))
    return render_template('dashboard.html')

@app.route("/api/dashboard_data")
@login_required
def dashboard_data():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    user_papel = session.get('papel')
    user_setor_id = session.get('user_setor_id')
    where_clause = "WHERE s.id = %s" if user_papel not in ['Administrador', 'Gerência'] else ""
    params = [user_setor_id] if user_papel not in ['Administrador', 'Gerência'] else []
    cursor.execute(f"SELECT date_trunc('month', MAX(data_lancamento)) as last_month FROM lancamentos l JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id {where_clause}", params)
    result = cursor.fetchone()
    target_date = result['last_month'] if result and result['last_month'] else datetime.now()
    target_month_str = target_date.strftime('%Y-%m-01')
    query_cards = f"""
        SELECT
            (SELECT COALESCE(SUM(valor_orcado), 0) FROM orcamentos o JOIN centros_custo cc ON o.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id WHERE o.ano = %s AND o.mes = %s {where_clause.replace('WHERE', 'AND')}) as total_orcado,
            (SELECT COALESCE(SUM(valor), 0) FROM lancamentos l JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id WHERE date_trunc('month', l.data_lancamento) = %s {where_clause.replace('WHERE', 'AND')}) as total_realizado;
    """
    cursor.execute(query_cards, [target_date.year, target_date.month] + params + [target_month_str] + params)
    cards_data = cursor.fetchone()
    query_anual = f"WITH meses AS (SELECT generate_series(date_trunc('month', current_date) - interval '11 months', date_trunc('month', current_date), '1 month')::date as mes), orcado AS (SELECT date_trunc('month', make_date(o.ano, o.mes, 1))::date m, sum(o.valor_orcado) v FROM orcamentos o JOIN centros_custo cc ON o.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id {where_clause} GROUP BY 1), realizado AS (SELECT date_trunc('month', l.data_lancamento)::date m, sum(l.valor) v FROM lancamentos l JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id {where_clause} GROUP BY 1) SELECT to_char(meses.mes, 'YYYY-MM') as label, COALESCE(o.v, 0) as orcado, COALESCE(r.v, 0) as realizado FROM meses LEFT JOIN orcado o ON meses.mes = o.m LEFT JOIN realizado r ON meses.mes = r.m ORDER BY meses.mes;"
    cursor.execute(query_anual, params + params)
    anual_data = cursor.fetchall()
    start_date_6m = (datetime.now() - relativedelta(months=5)).strftime('%Y-%m-01')
    where_conditions_projection = ["l.data_lancamento >= %s"]
    params_projection = [start_date_6m]
    if user_papel not in ['Administrador', 'Gerência']:
        where_conditions_projection.append("s.id = %s")
        params_projection.append(user_setor_id)
    final_where_projection = "WHERE " + " AND ".join(where_conditions_projection)
    query_cc_projection = f"""
        SELECT to_char(date_trunc('month', l.data_lancamento), 'YYYY-MM') as label, cc.nome as category, SUM(l.valor) as value
        FROM lancamentos l
        JOIN centros_custo cc ON l.centro_custo_id = cc.id
        JOIN setores s ON cc.setor_responsavel_id = s.id
        {final_where_projection}
        GROUP BY date_trunc('month', l.data_lancamento), cc.nome
        ORDER BY date_trunc('month', l.data_lancamento);
    """
    cursor.execute(query_cc_projection, params_projection)
    cc_projection_data = cursor.fetchall()
    query_gp_projection = f"""
        SELECT to_char(date_trunc('month', l.data_lancamento), 'YYYY-MM') as label, gp.nome as category, SUM(l.valor) as value
        FROM lancamentos l
        JOIN grupos_pagamento gp ON l.grupo_pagamento_id = gp.id
        JOIN centros_custo cc ON l.centro_custo_id = cc.id
        JOIN setores s ON cc.setor_responsavel_id = s.id
        {final_where_projection}
        GROUP BY date_trunc('month', l.data_lancamento), gp.nome
        ORDER BY date_trunc('month', l.data_lancamento);
    """
    cursor.execute(query_gp_projection, params_projection)
    gp_projection_data = cursor.fetchall()
    projection_labels = [(datetime.now() - relativedelta(months=i)).strftime('%Y-%m') for i in range(5, -1, -1)]
    cursor.close()
    conn.close()
    return jsonify({'cards': cards_data, 'anual': anual_data, 'projection_labels': projection_labels, 'cc_projection': cc_projection_data, 'gp_projection': gp_projection_data})

@app.route("/cadastros/lancamentos")
@login_required
def lancamentos_page(): return render_template('lancamentos.html')
@app.route("/api/lancamentos")
@login_required
def api_lancamentos():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    user_papel = session.get('papel')
    user_setor_id = session.get('user_setor_id')
    query = "SELECT l.id, to_char(l.data_lancamento, 'DD/MM/YYYY') as data_lancamento_formatada, l.descricao, l.valor, l.conta_fluxo, l.resultado_gerencial, cc.nome as centro_custo, gp.nome as grupo_pagamento FROM lancamentos l JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN grupos_pagamento gp ON l.grupo_pagamento_id = gp.id JOIN setores s ON cc.setor_responsavel_id = s.id"
    params = []
    if user_papel not in ['Administrador', 'Gerência']:
        query += " WHERE s.id = %s"
        params.append(user_setor_id)
    conta_fluxo = request.args.get('conta_fluxo')
    if conta_fluxo and conta_fluxo != 'all':
        query += " AND " if "WHERE" in query else " WHERE "
        query += " l.conta_fluxo = %s"
        params.append(conta_fluxo)
    query += " ORDER BY l.data_lancamento DESC, l.id DESC"
    cursor.execute(query, params)
    lancamentos = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(lancamentos)

@app.route("/api/contas_fluxo")
@login_required
def api_contas_fluxo():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT DISTINCT conta_fluxo FROM lancamentos WHERE conta_fluxo IS NOT NULL ORDER BY conta_fluxo")
    contas = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(contas)

@app.route("/cadastros/grupos-pagamento")
@login_required
@roles_required('Coordenador', 'Administrador')
def grupos_pagamento_page(): return render_template('grupos_pagamento.html')

@app.route("/api/grupos-pagamento", methods=['GET', 'POST'], endpoint='api_grupos_pagamento_list')
@login_required
@roles_required('Coordenador', 'Administrador')
def api_grupos_pagamento():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if request.method == 'GET':
        cursor.execute("SELECT * FROM grupos_pagamento ORDER BY nome")
        grupos = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(grupos)
    if request.method == 'POST':
        data = request.get_json()
        nome = data.get('nome')
        descricao = data.get('descricao')
        if not nome: return jsonify({'message': 'O nome do grupo é obrigatório.'}), 400
        try:
            cursor.execute("INSERT INTO grupos_pagamento (nome, descricao) VALUES (%s, %s) RETURNING id", (nome, descricao))
            new_id = cursor.fetchone()['id']
            conn.commit()
            return jsonify({'message': 'Grupo criado com sucesso!', 'id': new_id}), 201
        except psycopg2.IntegrityError:
            conn.rollback()
            return jsonify({'message': 'Um grupo com este nome já existe.'}), 409
        finally:
            cursor.close()
            conn.close()

@app.route("/api/grupos-pagamento/<int:grupo_id>", methods=['PUT', 'DELETE'], endpoint='api_grupo_pagamento_detail')
@login_required
@roles_required('Coordenador', 'Administrador')
def api_grupo_pagamento_detail(grupo_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'PUT':
        data = request.get_json()
        nome = data.get('nome')
        descricao = data.get('descricao')
        if not nome: return jsonify({'message': 'O nome do grupo é obrigatório.'}), 400
        try:
            cursor.execute("UPDATE grupos_pagamento SET nome = %s, descricao = %s WHERE id = %s", (nome, descricao, grupo_id))
            conn.commit()
            return jsonify({'message': 'Grupo atualizado com sucesso!'})
        except psycopg2.IntegrityError:
            conn.rollback()
            return jsonify({'message': 'Um grupo com este nome já existe.'}), 409
        finally:
            cursor.close()
            conn.close()
    if request.method == 'DELETE':
        try:
            cursor.execute("SELECT 1 FROM lancamentos WHERE grupo_pagamento_id = %s LIMIT 1", (grupo_id,))
            if cursor.fetchone(): return jsonify({'message': 'Não é possível excluir, grupo em uso por lançamentos.'}), 400
            cursor.execute("DELETE FROM grupos_pagamento WHERE id = %s", (grupo_id,))
            conn.commit()
            return jsonify({'message': 'Grupo excluído com sucesso!'})
        finally:
            cursor.close()
            conn.close()

@app.route("/cadastros/centros-custo")
@login_required
@roles_required('Coordenador', 'Administrador')
def centros_custo_page(): return render_template('centros_custo.html')

@app.route("/api/centros-custo", methods=['GET', 'POST'], endpoint='api_centros_custo_list')
@login_required
@roles_required('Coordenador', 'Administrador')
def api_centros_custo():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if request.method == 'GET':
        query = "SELECT cc.*, s.nome as setor_responsavel_nome FROM centros_custo cc JOIN setores s ON cc.setor_responsavel_id = s.id ORDER BY cc.nome"
        cursor.execute(query)
        centros_custo = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(centros_custo)
    if request.method == 'POST':
        data = request.get_json()
        nome = data.get('nome')
        codigo = data.get('codigo') or None
        setor_id = data.get('setor_id')
        descricao = data.get('descricao') or None
        if not nome or not setor_id: return jsonify({'message': 'Nome e Setor Responsável são obrigatórios.'}), 400
        try:
            cursor.execute("INSERT INTO centros_custo (nome, codigo, setor_responsavel_id, descricao) VALUES (%s, %s, %s, %s) RETURNING id", (nome, codigo, setor_id, descricao))
            new_id = cursor.fetchone()['id']
            conn.commit()
            return jsonify({'message': 'Centro de Custo criado com sucesso!', 'id': new_id}), 201
        except psycopg2.IntegrityError as e:
            conn.rollback()
            if 'centros_custo_codigo_key' in str(e): return jsonify({'message': 'Um Centro de Custo com este código já existe.'}), 409
            return jsonify({'message': 'Erro ao salvar no banco de dados.'}), 500
        finally:
            cursor.close()
            conn.close()

@app.route("/api/centros-custo/<int:cc_id>", methods=['DELETE'], endpoint='api_centro_custo_detail')
@login_required
@roles_required('Coordenador', 'Administrador')
def api_centro_custo_detail(cc_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT 1 FROM lancamentos WHERE centro_custo_id = %s LIMIT 1", (cc_id,))
    if cursor.fetchone(): return jsonify({'message': 'Não é possível excluir, Centro de Custo em uso por lançamentos.'}), 400
    cursor.execute("DELETE FROM centros_custo WHERE id = %s", (cc_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Centro de Custo excluído com sucesso!'})

@app.route("/cadastros/setores")
@login_required
@roles_required('Administrador')
def setores_page(): return render_template('setores.html')

@app.route("/api/setores", methods=['GET', 'POST'], endpoint='api_setores_list')
@login_required
def api_setores():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if request.method == 'GET':
        cursor.execute("SELECT id, nome FROM setores ORDER BY nome")
        setores = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(setores)
    if request.method == 'POST':
        if session.get('papel') != 'Administrador': return jsonify({'message': 'Acesso não autorizado para esta função.'}), 403
        data = request.get_json()
        nome = data.get('nome')
        if not nome: return jsonify({'message': 'O nome do setor é obrigatório.'}), 400
        try:
            cursor.execute("INSERT INTO setores (nome) VALUES (%s) RETURNING id", (nome,))
            new_id = cursor.fetchone()['id']
            conn.commit()
            return jsonify({'message': 'Setor criado com sucesso!', 'id': new_id}), 201
        except psycopg2.IntegrityError:
            conn.rollback()
            return jsonify({'message': 'Um setor com este nome já existe.'}), 409
        finally:
            cursor.close()
            conn.close()

@app.route("/api/setores/<int:setor_id>", methods=['PUT', 'DELETE'], endpoint='api_setor_detail')
@login_required
@roles_required('Administrador')
def api_setor_detail(setor_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'PUT':
        data = request.get_json()
        nome = data.get('nome')
        if not nome:
            return jsonify({'message': 'O nome do setor é obrigatório.'}), 400
        try:
            cursor.execute("UPDATE setores SET nome = %s WHERE id = %s", (nome, setor_id))
            conn.commit()
            return jsonify({'message': 'Setor atualizado com sucesso!'})
        except psycopg2.IntegrityError:
            conn.rollback()
            return jsonify({'message': 'Um setor com este nome já existe.'}), 409
        finally:
            cursor.close()
            conn.close()
    if request.method == 'DELETE':
        try:
            cursor.execute("SELECT 1 FROM usuarios WHERE setor_id = %s LIMIT 1", (setor_id,))
            if cursor.fetchone(): return jsonify({'message': 'Não é possível excluir, setor em uso por usuários.'}), 400
            cursor.execute("SELECT 1 FROM centros_custo WHERE setor_responsavel_id = %s LIMIT 1", (setor_id,))
            if cursor.fetchone(): return jsonify({'message': 'Não é possível excluir, setor em uso por centros de custo.'}), 400
            cursor.execute("DELETE FROM setores WHERE id = %s", (setor_id,))
            conn.commit()
            return jsonify({'message': 'Setor excluído com sucesso!'})
        finally:
            cursor.close()
            conn.close()

@app.route("/cadastros/usuarios")
@login_required
@roles_required('Administrador')
def usuarios_page(): return render_template('usuarios.html')

@app.route("/api/papeis", methods=['GET'], endpoint='api_papeis_list')
@login_required
@roles_required('Administrador')
def api_papeis():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT id, nome FROM papeis ORDER BY id")
    papeis = cursor.fetchall()
    cursor.close()
    conn.close()
    return jsonify(papeis)

@app.route("/api/usuarios", methods=['GET', 'POST'], endpoint='api_usuarios_list')
@login_required
@roles_required('Administrador')
def api_usuarios():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    if request.method == 'GET':
        query = "SELECT u.id, u.nome_completo, u.email, s.nome as setor_nome, p.nome as papel_nome FROM usuarios u LEFT JOIN setores s ON u.setor_id = s.id LEFT JOIN papeis p ON u.papel_id = p.id ORDER BY u.nome_completo"
        cursor.execute(query)
        usuarios = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(usuarios)
    if request.method == 'POST':
        data = request.get_json()
        nome = data.get('nome_completo')
        email = data.get('email')
        senha = data.get('senha')
        setor_id = data.get('setor_id')
        papel_id = data.get('papel_id')
        if not all([nome, email, senha, setor_id, papel_id]): return jsonify({'message': 'Todos os campos são obrigatórios.'}), 400
        hash_senha = generate_password_hash(senha)
        try:
            cursor.execute("INSERT INTO usuarios (nome_completo, email, hash_senha, setor_id, papel_id) VALUES (%s, %s, %s, %s, %s) RETURNING id", (nome, email, hash_senha, setor_id, papel_id))
            new_id = cursor.fetchone()['id']
            conn.commit()
            return jsonify({'message': 'Usuário criado com sucesso!', 'id': new_id}), 201
        except psycopg2.IntegrityError:
            conn.rollback()
            return jsonify({'message': 'Um usuário com este e-mail já existe.'}), 409
        finally:
            cursor.close()
            conn.close()

@app.route("/api/usuarios/<int:usuario_id>", methods=['DELETE'], endpoint='api_usuario_detail')
@login_required
@roles_required('Administrador')
def api_usuario_detail(usuario_id):
    if usuario_id == session.get('user_id'): return jsonify({'message': 'Você não pode excluir a si mesmo.'}), 400
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'message': 'Usuário excluído com sucesso!'})

# --- ROTAS DE IMPORTAÇÃO ---
@app.route("/importar")
@login_required
@roles_required('Coordenador', 'Administrador')
def importar_page(): return render_template('importar.html')
@app.route('/api/import', methods=['POST'])
@login_required
@roles_required('Coordenador', 'Administrador')
def upload_file():
    if 'arquivo' not in request.files: return jsonify({'log': 'Nenhum arquivo enviado.'}), 400
    file = request.files['arquivo']
    tipo_arquivo = request.form.get('tipo_arquivo')
    if file.filename == '': return jsonify({'log': 'Nenhum arquivo selecionado.'}), 400
    if file and tipo_arquivo:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        log_messages = []
        try:
            df = pd.read_excel(filepath, header=None)
            log_messages.append(f"Arquivo '{filename}' lido com sucesso. {len(df)} linhas encontradas.")
            
            conn = get_db_connection()
            process_file(df, conn, log_messages)
            conn.close()
        except Exception as e:
            log_messages.append(f"ERRO: Falha ao processar o arquivo. Detalhes: {str(e)}")
        
        if os.path.exists(filepath):
            os.remove(filepath)
            
        return jsonify({'log': "\n".join(log_messages)})
    return jsonify({'log': 'Erro desconhecido.'}), 500

def parse_custom_date(date_str):
    """Função para converter datas no formato 'mês/ano' ou 'dd/mm/aaaa'."""
    month_map = {
        'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
        'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12
    }
    try:
        return pd.to_datetime(date_str, dayfirst=True).date()
    except (ValueError, TypeError):
        parts = str(date_str).lower().strip().split('/')
        if len(parts) == 2:
            month_str, year_str = parts
            if month_str in month_map:
                month = month_map[month_str]
                year = int(f"20{year_str}")
                return datetime(year, month, 1).date()
    return None

def process_file(df, conn, log):
    log.append("Iniciando processamento de arquivo...")
    cursor = conn.cursor()
    sucesso_lancamentos = 0
    sucesso_orcamentos = 0
    falhas = 0
    cc_cache = {}
    gp_cache = {}

    for index, row in df.iterrows():
        try:
            conta_fluxo_desc = str(row.get(0, '')).strip()
            resultado_gerencial = str(row.get(1, '')).strip()
            grupo_pagamento_nome = str(row.get(2, '')).strip()
            competencia_str = str(row.get(3, '')).strip()
            data_movimentacao_str = str(row.get(4, '')).strip()
            fornecedor = str(row.get(5, '')).strip()
            descricao_extra = str(row.get(6, '')).strip()
            cc_str = str(row.get(8, '')).strip()
            
            # CORREÇÃO APLICADA AQUI
            valor_realizado = limpar_e_converter_moeda(row.get(7))
            valor_orcado = limpar_e_converter_moeda(row.get(9))

            competencia_date = parse_custom_date(competencia_str)
            if not competencia_date or "Total" in conta_fluxo_desc:
                continue
            
            cc_match = re.search(r'(\d+)', cc_str)
            if not cc_match:
                falhas += 1
                log.append(f"Linha {index+1}: Não foi possível extrair o código do Centro de Custo de '{cc_str}'. Pulando.")
                continue
            centro_custo_codigo = cc_match.group(1)

            if valor_orcado != 0:
                if centro_custo_codigo not in cc_cache:
                    cursor.execute("SELECT id FROM centros_custo WHERE codigo = %s", (centro_custo_codigo,))
                    cc_id_result = cursor.fetchone()
                    if not cc_id_result:
                        cursor.execute("INSERT INTO centros_custo (nome, codigo, setor_responsavel_id) VALUES (%s, %s, %s) RETURNING id", (cc_str, centro_custo_codigo, 1)) # Setor 1 como padrão
                        cc_id_result = cursor.fetchone()
                        conn.commit()
                    cc_cache[centro_custo_codigo] = cc_id_result[0]
                cc_id = cc_cache[centro_custo_codigo]

                if grupo_pagamento_nome not in gp_cache:
                    cursor.execute("SELECT id FROM grupos_pagamento WHERE nome = %s", (grupo_pagamento_nome,))
                    gp_id_result = cursor.fetchone()
                    if not gp_id_result:
                        cursor.execute("INSERT INTO grupos_pagamento (nome) VALUES (%s) RETURNING id", (grupo_pagamento_nome,))
                        gp_id_result = cursor.fetchone()
                        conn.commit()
                    gp_cache[grupo_pagamento_nome] = gp_id_result[0]
                gp_id = gp_cache[grupo_pagamento_nome]
                
                cursor.execute(
                    "INSERT INTO orcamentos (ano, mes, centro_custo_id, grupo_pagamento_id, valor_orcado) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (ano, mes, centro_custo_id, grupo_pagamento_id) DO UPDATE SET valor_orcado = EXCLUDED.valor_orcado",
                    (competencia_date.year, competencia_date.month, cc_id, gp_id, valor_orcado)
                )
                sucesso_orcamentos += 1

            if valor_realizado != 0:
                data_lancamento = parse_custom_date(data_movimentacao_str) or competencia_date

                if centro_custo_codigo not in cc_cache:
                    cursor.execute("SELECT id FROM centros_custo WHERE codigo = %s", (centro_custo_codigo,))
                    cc_id_result = cursor.fetchone()
                    if not cc_id_result:
                        cursor.execute("INSERT INTO centros_custo (nome, codigo, setor_responsavel_id) VALUES (%s, %s, %s) RETURNING id", (cc_str, centro_custo_codigo, 1)) # Setor 1 como padrão
                        cc_id_result = cursor.fetchone()
                        conn.commit()
                    cc_cache[centro_custo_codigo] = cc_id_result[0]
                cc_id = cc_cache[centro_custo_codigo]

                if grupo_pagamento_nome not in gp_cache:
                    cursor.execute("SELECT id FROM grupos_pagamento WHERE nome = %s", (grupo_pagamento_nome,))
                    gp_id_result = cursor.fetchone()
                    if not gp_id_result:
                        cursor.execute("INSERT INTO grupos_pagamento (nome) VALUES (%s) RETURNING id", (grupo_pagamento_nome,))
                        gp_id_result = cursor.fetchone()
                        conn.commit()
                    gp_cache[grupo_pagamento_nome] = gp_id_result[0]
                gp_id = gp_cache[grupo_pagamento_nome]

                descricao_final = f"{fornecedor} - {descricao_extra}".strip(' -')
                
                cursor.execute(
                    "INSERT INTO lancamentos (data_lancamento, descricao, centro_custo_id, grupo_pagamento_id, valor, conta_fluxo, resultado_gerencial, usuario_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (data_lancamento, descricao_final, cc_id, gp_id, valor_realizado, conta_fluxo_desc, resultado_gerencial, session.get('user_id'))
                )
                sucesso_lancamentos += 1

        except Exception as e:
            falhas += 1
            log.append(f"Linha {index+1}: Erro ao processar. Detalhes: {e}")
            conn.rollback()

    conn.commit()
    cursor.close()
    log.append(f"Processamento concluído. Lançamentos: {sucesso_lancamentos} | Orçamentos: {sucesso_orcamentos} | Falhas: {falhas}.")

# --- ROTAS PARA TROCA DE SENHA ---
@app.route("/trocar-senha")
@login_required
def trocar_senha_page():
    if not session.get('primeiro_login', False):
        return redirect(url_for('dashboard'))
    return render_template('trocar_senha.html')

@app.route("/api/trocar-senha", methods=['POST'])
@login_required
def api_trocar_senha():
    data = request.get_json()
    senha_antiga = data.get('senha_antiga')
    nova_senha = data.get('nova_senha')
    confirmar_senha = data.get('confirmar_senha')

    if not all([senha_antiga, nova_senha, confirmar_senha]):
        return jsonify({'message': 'Todos os campos são obrigatórios.'}), 400
    if nova_senha != confirmar_senha:
        return jsonify({'message': 'A nova senha e a confirmação não correspondem.'}), 400

    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT hash_senha FROM usuarios WHERE id = %s", (user_id,))
    user = cursor.fetchone()

    if not user or not check_password_hash(user['hash_senha'], senha_antiga):
        cursor.close()
        conn.close()
        return jsonify({'message': 'A senha atual está incorreta.'}), 401

    novo_hash = generate_password_hash(nova_senha)
    cursor.execute("UPDATE usuarios SET hash_senha = %s, primeiro_login = FALSE WHERE id = %s", (novo_hash, user_id))
    conn.commit()
    cursor.close()
    conn.close()
    session['primeiro_login'] = False
    return jsonify({'message': 'Senha alterada com sucesso! Você será redirecionado.'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
