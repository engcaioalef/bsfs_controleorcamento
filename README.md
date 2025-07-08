<p align="center">
  <img src="assets/banner.png" alt="Banner do Projeto Sistema de Controle Orçamentário"/>
</p>

<p align="center">
  <img alt="Status do Projeto" src="https://img.shields.io/badge/STATUS-EM%20DESENVOLVIMENTO-yellow">
  <img alt="Linguagem" src="https://img.shields.io/badge/LINGUAGEM-PYTHON-blue">
  <img alt="Framework" src="https://img.shields.io/badge/FRAMEWORK-FLASK-gray">
  <a href="https://opensource.org/licenses/MIT">
    <img alt="Licença" src="https://img.shields.io/badge/License-MIT-yellow.svg">
  </a>
</p>

## 📝 Descrição do Projeto

Este projeto é uma aplicação web completa para gestão de orçamentos e finanças. Desenvolvido com Flask e PostgreSQL, ele permite o controle detalhado de custos, comparação entre orçado e realizado, e gerenciamento de acessos por função.

---

## ✨ Funcionalidades

-   **🔑 Autenticação Segura:** Login, logout e troca de senha obrigatória no primeiro acesso.
-   **🔐 Controle de Acesso por Função:** Níveis de permissão para Administradores, Gerentes e Coordenadores.
-   **📊 Dashboard Interativo:** KPIs e gráficos dinâmicos para análise visual dos dados financeiros.
-   **🗂️ Módulos de Cadastro:** Gerenciamento completo (CRUD) de Usuários, Setores, Centros de Custo e mais.
-   **📄 Importação de Dados:** Ferramenta para upload e processamento de planilhas Excel (`.xlsx`) em lote.

---

## 🏛️ Arquitetura do Sistema

Aqui você pode inserir o diagrama que criou no Canva para ilustrar a arquitetura.

<p align="center">
  <img src="assets/arquitetura.png" alt="Diagrama da Arquitetura do Sistema"/>
</p>

---

## 🛠️ Tecnologias Utilizadas

| Ferramenta | Descrição |
| :---: | --- |
| **Python** | Linguagem principal do backend. |
| **Flask** | Micro-framework web para a construção da API. |
| **PostgreSQL** | Banco de dados relacional para armazenamento dos dados. |
| **Pandas** | Biblioteca para manipulação e processamento dos arquivos Excel. |
| **HTML/CSS/JS**| Tecnologias padrão para a construção do frontend. |

---

## 🚀 Como Executar

Siga os passos abaixo para configurar e executar o projeto em seu ambiente local.

```bash
# 1. Clone o repositório
git clone [https://github.com/engcaioalef/bsfs_controleorcamento](https://github.com/engcaioalef/bsfs_controleorcamento)

# 2. Navegue até a pasta do projeto
cd seu-repositorio

# 3. Crie e ative um ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 4. Instale as dependências
pip install -r requirements.txt

# 5. Configure as variáveis de ambiente em config.py
# (Siga as instruções da seção de configuração)

# 6. Execute a aplicação
python run.py
```

---

## 📄 Licença

Distribuído sob a licença MIT. Veja `LICENSE` para mais informações.
