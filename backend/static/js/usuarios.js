document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('form-usuario');
    const tableBody = document.getElementById('usuarios-table-body');
    const setorSelect = document.getElementById('setor');
    const papelSelect = document.getElementById('papel');

    // Função para limpar o formulário
    const resetForm = () => {
        form.reset();
        document.getElementById('usuario-id').value = '';
    };

    // Função genérica para preencher um select com dados de uma API
    const preencherSelect = async (selectElement, apiUrl, placeholder) => {
        try {
            const response = await fetch(apiUrl);
            if (!response.ok) throw new Error(`Falha ao buscar dados de ${apiUrl}`);
            const data = await response.json();

            selectElement.innerHTML = `<option value="">${placeholder}</option>`;
            data.forEach(item => {
                const option = document.createElement('option');
                option.value = item.id;
                option.textContent = item.nome;
                selectElement.appendChild(option);
            });
        } catch (error) {
            console.error(`Erro ao carregar ${placeholder}:`, error);
            selectElement.innerHTML = `<option value="">Erro ao carregar</option>`;
        }
    };

    // Função para carregar os usuários e preencher a tabela
    const carregarUsuarios = async () => {
        try {
            const response = await fetch('/api/usuarios');
            if (!response.ok) throw new Error('Falha ao buscar usuários.');
            const usuarios = await response.json();

            tableBody.innerHTML = '';
            if (usuarios.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="5" class="text-center">Nenhum usuário encontrado.</td></tr>`;
                return;
            }

            usuarios.forEach(user => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${user.nome_completo}</td>
                    <td>${user.email}</td>
                    <td>${user.setor_nome || 'N/A'}</td>
                    <td>${user.papel_nome || 'N/A'}</td>
                    <td class="action-buttons">
                        <button class="btn-action btn-delete" data-id="${user.id}">Excluir</button>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        } catch (error) {
            console.error('Erro ao carregar usuários:', error);
        }
    };

    // Evento de submit do formulário para criar um novo usuário
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const data = {
            nome_completo: document.getElementById('nome_completo').value.trim(),
            email: document.getElementById('email').value.trim(),
            senha: document.getElementById('senha').value,
            setor_id: setorSelect.value,
            papel_id: papelSelect.value
        };

        if (Object.values(data).some(value => !value)) {
            alert('Todos os campos são obrigatórios.');
            return;
        }

        try {
            const response = await fetch('/api/usuarios', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.message || 'Erro ao salvar usuário.');

            alert(result.message);
            resetForm();
            carregarUsuarios();
        } catch (error) {
            console.error('Erro ao criar usuário:', error);
            alert(error.message);
        }
    });

    // Evento na tabela para o botão de deletar
    tableBody.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-delete')) {
            const usuarioId = e.target.dataset.id;
            if (confirm('Tem certeza que deseja excluir este usuário?')) {
                try {
                    const response = await fetch(`/api/usuarios/${usuarioId}`, { method: 'DELETE' });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.message);
                    alert(result.message);
                    carregarUsuarios();
                } catch (error) {
                    console.error('Erro ao excluir usuário:', error);
                    alert(error.message);
                }
            }
        }
    });

    // Carrega os dados iniciais (Setores, Papéis e Usuários)
    const init = () => {
        preencherSelect(setorSelect, '/api/setores', 'Selecione um setor');
        preencherSelect(papelSelect, '/api/papeis', 'Selecione um papel');
        carregarUsuarios();
    };

    init();
});
