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
        return decorated_function
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
    
    today = datetime.now()
    
    cursor.execute(f"SELECT MAX(ano) as max_year FROM orcamentos o JOIN centros_custo cc ON o.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id {where_clause}", params)
    max_year_result = cursor.fetchone()
    current_year = max_year_result['max_year'] if max_year_result and max_year_result['max_year'] else today.year
    previous_year = current_year - 1
    
    query_orcado_anual = f"SELECT COALESCE(SUM(o.valor_orcado), 0) as total FROM orcamentos o JOIN centros_custo cc ON o.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id WHERE o.ano = %s {where_clause.replace('WHERE', 'AND')}"
    cursor.execute(query_orcado_anual, [current_year] + params)
    total_orcado_anual = cursor.fetchone()['total']
    
    query_realizado_anual = f"SELECT COALESCE(SUM(l.valor), 0) as total FROM lancamentos l JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id WHERE EXTRACT(YEAR FROM l.data_lancamento) = %s {where_clause.replace('WHERE', 'AND')}"
    cursor.execute(query_realizado_anual, [current_year] + params)
    total_realizado_anual = cursor.fetchone()['total']
    
    cursor.execute(f"SELECT date_trunc('month', MAX(data_lancamento)) as last_month FROM lancamentos l JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id {where_clause}", params)
    result = cursor.fetchone()
    target_date = result['last_month'] if result and result['last_month'] else today
    target_month_str = target_date.strftime('%Y-%m-01')
    
    query_cards = f"""
        SELECT
            (SELECT COALESCE(SUM(valor_orcado), 0) FROM orcamentos o JOIN centros_custo cc ON o.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id WHERE o.ano = %s AND o.mes = %s {where_clause.replace('WHERE', 'AND')}) as total_orcado,
            (SELECT COALESCE(SUM(valor), 0) FROM lancamentos l JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id WHERE date_trunc('month', l.data_lancamento) = %s {where_clause.replace('WHERE', 'AND')}) as total_realizado;
    """
    cursor.execute(query_cards, [target_date.year, target_date.month] + params + [target_month_str] + params)
    cards_data = cursor.fetchone()
    cards_data['total_orcado_anual'] = total_orcado_anual
    cards_data['total_realizado_anual'] = total_realizado_anual

    query_yoy = f"""
        WITH meses AS (SELECT generate_series(1, 12) as mes),
        orcado_atual AS (SELECT mes, COALESCE(SUM(valor_orcado), 0) as valor FROM orcamentos o JOIN centros_custo cc ON o.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id WHERE ano = %s {where_clause.replace('WHERE', 'AND')} GROUP BY mes),
        realizado_atual AS (SELECT EXTRACT(MONTH FROM data_lancamento) as mes, COALESCE(SUM(valor), 0) as valor FROM lancamentos l JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id WHERE EXTRACT(YEAR FROM data_lancamento) = %s {where_clause.replace('WHERE', 'AND')} GROUP BY mes),
        realizado_anterior AS (SELECT EXTRACT(MONTH FROM data_lancamento) as mes, COALESCE(SUM(valor), 0) as valor FROM lancamentos l JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id WHERE EXTRACT(YEAR FROM data_lancamento) = %s {where_clause.replace('WHERE', 'AND')} GROUP BY mes)
        SELECT m.mes, COALESCE(oa.valor, 0) as orcado_atual, COALESCE(ra.valor, 0) as realizado_atual, COALESCE(ran.valor, 0) as realizado_anterior
        FROM meses m LEFT JOIN orcado_atual oa ON m.mes = oa.mes LEFT JOIN realizado_atual ra ON m.mes = ra.mes LEFT JOIN realizado_anterior ran ON m.mes = ran.mes ORDER BY m.mes;
    """
    cursor.execute(query_yoy, [current_year] + params + [current_year] + params + [previous_year] + params)
    yoy_data = cursor.fetchall()

    start_date_6m = (today - relativedelta(months=5)).strftime('%Y-%m-01')
    where_conditions_projection = ["l.data_lancamento >= %s"]
    params_projection = [start_date_6m]
    if user_papel not in ['Administrador', 'Gerência']:
        where_conditions_projection.append("s.id = %s")
        params_projection.append(user_setor_id)
    final_where_projection = "WHERE " + " AND ".join(where_conditions_projection)
    
    query_cc_projection = f"SELECT to_char(date_trunc('month', l.data_lancamento), 'YYYY-MM') as label, cc.id as category_id, cc.nome as category, SUM(l.valor) as value FROM lancamentos l JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id {final_where_projection} GROUP BY 1, 2, 3 ORDER BY 1;"
    cursor.execute(query_cc_projection, params_projection)
    cc_projection_data = cursor.fetchall()
    
    query_gp_projection = f"SELECT to_char(date_trunc('month', l.data_lancamento), 'YYYY-MM') as label, gp.id as category_id, gp.nome as category, SUM(l.valor) as value FROM lancamentos l JOIN grupos_pagamento gp ON l.grupo_pagamento_id = gp.id JOIN centros_custo cc ON l.centro_custo_id = cc.id JOIN setores s ON cc.setor_responsavel_id = s.id {final_where_projection} GROUP BY 1, 2, 3 ORDER BY 1;"
    cursor.execute(query_gp_projection, params_projection)
    gp_projection_data = cursor.fetchall()
    
    projection_labels = [(today - relativedelta(months=i)).strftime('%Y-%m') for i in range(5, -1, -1)]

    cursor.execute("SELECT id, nome FROM centros_custo ORDER BY nome")
    centros_custo = cursor.fetchall()
    cursor.execute("SELECT id, nome FROM grupos_pagamento ORDER BY nome")
    grupos_pagamento = cursor.fetchall()

    cursor.close()
    conn.close()
    
    return jsonify({
        'cards': cards_data, 
        'yoy_data': yoy_data,
        'projection_labels': projection_labels, 
        'cc_projection': cc_projection_data, 
        'gp_projection': gp_projection_data,
        'filters': {
            'centros_custo': centros_custo,
            'grupos_pagamento': grupos_pagamento
        },
        'years': {
            'current': current_year,
            'previous': previous_year
        }
    })

@app.route("/api/lancamentos_filtrados")
@login_required
def api_lancamentos_filtrados():
    filter_type = request.args.get('type')
    filter_id = request.args.get('id')
    period_days_str = request.args.get('period', '365')

    if not filter_type or not filter_id:
        return jsonify([])

    try:
        period_days = int(period_days_str)
    except (ValueError, TypeError):
        period_days = 365

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    params = [filter_id, period_days]
    
    where_conditions = []
    if filter_type == 'centro_custo':
        where_conditions.append("l.centro_custo_id = %s")
    elif filter_type == 'grupo_pagamento':
        where_conditions.append("l.grupo_pagamento_id = %s")
    else:
        return jsonify({'message': 'Tipo de filtro inválido'}), 400
    
    where_conditions.append("l.data_lancamento >= current_date - interval '%s days'")

    query = f"""
        SELECT l.id, to_char(l.data_lancamento, 'DD/MM/YYYY') as data, l.descricao, l.valor, 
               cc.nome as centro_custo, gp.nome as grupo_pagamento
        FROM lancamentos l
        JOIN centros_custo cc ON l.centro_custo_id = cc.id
        JOIN grupos_pagamento gp ON l.grupo_pagamento_id = gp.id
        WHERE {' AND '.join(where_conditions)}
        ORDER BY l.data_lancamento DESC
    """
    
    cursor.execute(query, tuple(params))
    lancamentos = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify(lancamentos)


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

@app.route("/cadastros/grupos-pagamento", endpoint='grupos_pagamento_page')
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

@app.route("/cadastros/centros-custo", endpoint='centros_custo_page')
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

@app.route("/api/centros-custo/<int:cc_id>", methods=['PUT', 'DELETE'], endpoint='api_centro_custo_detail')
@login_required
@roles_required('Coordenador', 'Administrador')
def api_centro_custo_detail(cc_id):
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    if request.method == 'PUT':
        data = request.get_json()
        nome = data.get('nome')
        codigo = data.get('codigo') or None
        setor_id = data.get('setor_id')
        descricao = data.get('descricao') or None
        if not nome or not setor_id:
            return jsonify({'message': 'Nome e Setor Responsável são obrigatórios.'}), 400
        try:
            cursor.execute(
                "UPDATE centros_custo SET nome = %s, codigo = %s, setor_responsavel_id = %s, descricao = %s WHERE id = %s",
                (nome, codigo, setor_id, descricao, cc_id)
            )
            conn.commit()
            return jsonify({'message': 'Centro de Custo atualizado com sucesso!'})
        except psycopg2.IntegrityError as e:
            conn.rollback()
            if 'centros_custo_codigo_key' in str(e):
                return jsonify({'message': 'Um Centro de Custo com este código já existe.'}), 409
            return jsonify({'message': 'Erro ao salvar no banco de dados.'}), 500
        finally:
            cursor.close()
            conn.close()

    if request.method == 'DELETE':
        try:
            cursor.execute("SELECT 1 FROM lancamentos WHERE centro_custo_id = %s LIMIT 1", (cc_id,))
            if cursor.fetchone():
                return jsonify({'message': 'Não é possível excluir, Centro de Custo em uso por lançamentos.'}), 400
            cursor.execute("DELETE FROM centros_custo WHERE id = %s", (cc_id,))
            conn.commit()
            return jsonify({'message': 'Centro de Custo excluído com sucesso!'})
        finally:
            cursor.close()
            conn.close()

@app.route("/cadastros/setores", endpoint='setores_page')
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

@app.route("/cadastros/usuarios", endpoint='usuarios_page')
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
@app.route("/importar", endpoint='importar_page')
@login_required
@roles_required('Coordenador', 'Administrador')
def importar_page(): return render_template('importar.html')

@app.route('/api/import', methods=['POST'])
@login_required
@roles_required('Coordenador', 'Administrador')
def upload_file():
    if 'arquivo' not in request.files: return jsonify({'log': 'Nenhum arquivo enviado.'}), 400
    file = request.files['arquivo']
    criar_novos = request.form.get('criar_novos') == 'true'
    
    if file.filename == '': return jsonify({'log': 'Nenhum arquivo selecionado.'}), 400
    
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        log_messages = []
        try:
            df = pd.read_excel(filepath, header=None)
            log_messages.append(f"Arquivo '{filename}' lido com sucesso. {len(df)} linhas encontradas.")
            
            conn = get_db_connection()
            process_file(df, conn, log_messages, criar_novos)
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

def limpar_e_converter_moeda(valor):
    """
    Função para converter valores monetários (que podem ser números ou texto) para float.
    """
    if isinstance(valor, (int, float)):
        return float(valor)

    if valor is None or pd.isna(valor):
        return 0.0
    
    s = str(valor).strip()
    if not s:
        return 0.0

    # Lógica para formato brasileiro (ex: "1.234,56")
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    
    s = re.sub(r'[^\d.-]', '', s)

    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0

def process_file(df, conn, log, criar_novos):
    log.append("Iniciando processamento de arquivo...")
    cursor = conn.cursor()
    sucesso_lancamentos = 0
    sucesso_orcamentos = 0
    falhas = 0
    
    # Cache inicial
    cursor.execute("SELECT codigo, id FROM centros_custo")
    cc_cache = {row[0]: row[1] for row in cursor.fetchall()}
    cursor.execute("SELECT nome, id FROM grupos_pagamento")
    gp_cache = {row[0]: row[1] for row in cursor.fetchall()}

    for index, row in df.iterrows():
        try:
            conta_fluxo_desc = str(row.get(0, '')).strip()
            resultado_gerencial = str(row.get(1, '')).strip()
            grupo_pagamento_nome = str(row.get(2, '')).strip()
            competencia_str = str(row.get(3, '')).strip()
            data_movimentacao_str = str(row.get(4, '')).strip()
            
            fornecedor_val = row.get(5)
            fornecedor = str(fornecedor_val).strip() if pd.notna(fornecedor_val) and fornecedor_val else ''
            
            descricao_extra_val = row.get(6)
            descricao_extra = str(descricao_extra_val).strip() if pd.notna(descricao_extra_val) and descricao_extra_val else ''

            cc_str = str(row.get(8, '')).strip()
            
            valor_realizado = limpar_e_converter_moeda(row.get(7))
            valor_orcado = limpar_e_converter_moeda(row.get(9))

            competencia_date = parse_custom_date(competencia_str)
            if not competencia_date or "Total" in conta_fluxo_desc:
                continue
            
            if not cc_str or not grupo_pagamento_nome:
                falhas += 1
                log.append(f"Linha {index+1}: Centro de Custo ou Grupo de Pagamento vazio. Pulando.")
                continue

            centro_custo_nome = cc_str
            cc_match = re.search(r'(\d+)', cc_str)
            centro_custo_codigo = cc_match.group(1) if cc_match else centro_custo_nome

            # --- VERIFICAÇÃO E CRIAÇÃO DE ITENS ---
            if centro_custo_codigo not in cc_cache:
                if criar_novos:
                    cursor.execute("INSERT INTO centros_custo (nome, codigo, setor_responsavel_id) VALUES (%s, %s, %s) RETURNING id", (centro_custo_nome, centro_custo_codigo, 1))
                    cc_id = cursor.fetchone()[0]
                    cc_cache[centro_custo_codigo] = cc_id
                    conn.commit()
                    log.append(f"Novo Centro de Custo '{centro_custo_nome}' criado.")
                else:
                    falhas += 1
                    log.append(f"Linha {index+1}: Centro de Custo '{centro_custo_nome}' não encontrado. Pulando.")
                    continue
            cc_id = cc_cache[centro_custo_codigo]

            if grupo_pagamento_nome not in gp_cache:
                if criar_novos:
                    cursor.execute("INSERT INTO grupos_pagamento (nome) VALUES (%s) RETURNING id", (grupo_pagamento_nome,))
                    gp_id = cursor.fetchone()[0]
                    gp_cache[grupo_pagamento_nome] = gp_id
                    conn.commit()
                    log.append(f"Novo Grupo de Pagamento '{grupo_pagamento_nome}' criado.")
                else:
                    falhas += 1
                    log.append(f"Linha {index+1}: Grupo de Pagamento '{grupo_pagamento_nome}' não encontrado. Pulando.")
                    continue
            gp_id = gp_cache[grupo_pagamento_nome]

            # --- PROCESSAR ORÇAMENTO ---
            if valor_orcado != 0:
                cursor.execute(
                    "INSERT INTO orcamentos (ano, mes, centro_custo_id, grupo_pagamento_id, valor_orcado) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (ano, mes, centro_custo_id, grupo_pagamento_id) DO UPDATE SET valor_orcado = EXCLUDED.valor_orcado",
                    (competencia_date.year, competencia_date.month, cc_id, gp_id, valor_orcado)
                )
                sucesso_orcamentos += 1

            # --- PROCESSAR LANÇAMENTO ---
            if valor_realizado != 0:
                data_lancamento = parse_custom_date(data_movimentacao_str) or competencia_date
                descricao_parts = [p for p in [fornecedor, descricao_extra] if p]
                descricao_final = " - ".join(descricao_parts)
                
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
@app.route("/trocar-senha", endpoint='trocar_senha_page')
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
