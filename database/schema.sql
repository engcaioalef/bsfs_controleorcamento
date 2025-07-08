-- SQL Schema for Budget Management System
-- Database: PostgreSQL

-- Apaga as tabelas se elas já existirem, para permitir uma recriação limpa.
-- A ordem é importante para respeitar as chaves estrangeiras.
DROP TABLE IF EXISTS lancamentos;
DROP TABLE IF EXISTS orcamentos;
DROP TABLE IF EXISTS usuarios;
DROP TABLE IF EXISTS centros_custo;
DROP TABLE IF EXISTS setores;
DROP TABLE IF EXISTS grupos_pagamento;
DROP TABLE IF EXISTS papeis;


-- Tabela para os papéis (níveis de acesso) dos usuários
-- Define os diferentes tipos de permissão no sistema.
CREATE TABLE papeis (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(50) UNIQUE NOT NULL -- Ex: 'Básico', 'Coordenador', 'Administrador'
);

-- Inserindo os papéis padrão que o sistema utilizará.
INSERT INTO papeis (nome) VALUES ('Básico'), ('Coordenador'), ('Administrador');


-- Tabela para os setores da empresa
-- Organiza os usuários e os custos por departamento.
CREATE TABLE setores (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) UNIQUE NOT NULL -- Ex: 'TI', 'Manutenção', 'Financeiro', 'Gerência'
);


-- Tabela de usuários
-- Armazena as informações de login e os dados dos usuários.
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nome_completo VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hash_senha VARCHAR(255) NOT NULL,
    setor_id INT,
    papel_id INT NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    primeiro_login BOOLEAN DEFAULT TRUE, -- Para forçar a troca de senha no primeiro acesso
    data_criacao TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (setor_id) REFERENCES setores(id),
    FOREIGN KEY (papel_id) REFERENCES papeis(id)
);


-- Tabela para Centros de Custo
-- Agrupa as despesas em unidades contábeis específicas.
CREATE TABLE centros_custo (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) NOT NULL,
    codigo VARCHAR(50) UNIQUE,
    descricao TEXT,
    setor_responsavel_id INT, -- Um setor pode ser o "dono" do centro de custo
    FOREIGN KEY (setor_responsavel_id) REFERENCES setores(id)
);


-- Tabela para Grupos de Pagamento
-- Classifica a natureza dos gastos. Ex: 'Despesas com Pessoal', 'Viagens', 'Infraestrutura'.
CREATE TABLE grupos_pagamento (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) UNIQUE NOT NULL,
    descricao TEXT
);


-- Tabela para armazenar o orçamento
-- Guarda os valores planejados para cada combinação de centro de custo e grupo de pagamento.
CREATE TABLE orcamentos (
    id SERIAL PRIMARY KEY,
    ano INT NOT NULL,
    mes INT NOT NULL,
    centro_custo_id INT NOT NULL,
    grupo_pagamento_id INT NOT NULL,
    valor_orcado NUMERIC(15, 2) NOT NULL,
    data_importacao TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    -- Garante que não haja orçamentos duplicados para o mesmo período/centro/grupo
    CONSTRAINT orcamento_unico UNIQUE (ano, mes, centro_custo_id, grupo_pagamento_id),
    FOREIGN KEY (centro_custo_id) REFERENCES centros_custo(id) ON DELETE CASCADE,
    FOREIGN KEY (grupo_pagamento_id) REFERENCES grupos_pagamento(id) ON DELETE CASCADE
);


-- Tabela para registrar os gastos (o "realizado")
-- Armazena cada transação ou despesa que ocorre.
CREATE TABLE lancamentos (
    id SERIAL PRIMARY KEY,
    descricao TEXT NOT NULL,
    valor NUMERIC(15, 2) NOT NULL,
    data_lancamento DATE NOT NULL,
    centro_custo_id INT NOT NULL,
    grupo_pagamento_id INT NOT NULL,
    usuario_id INT, -- Quem registrou o lançamento
    data_registro TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (centro_custo_id) REFERENCES centros_custo(id) ON DELETE CASCADE,
    FOREIGN KEY (grupo_pagamento_id) REFERENCES grupos_pagamento(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
);

-- Mensagem final para o log
\echo 'Estrutura do banco de dados criada com sucesso!'
