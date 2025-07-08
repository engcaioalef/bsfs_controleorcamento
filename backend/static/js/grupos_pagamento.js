document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('form-grupo-pagamento');
    const tableBody = document.getElementById('grupos-table-body');
    const formTitle = document.getElementById('form-title');
    const nomeInput = document.getElementById('nome');
    const descricaoInput = document.getElementById('descricao');
    const grupoIdInput = document.getElementById('grupo-id');
    const btnCancelar = document.getElementById('btn-cancelar');

    // Função para limpar o formulário e resetar para o modo de adição
    const resetForm = () => {
        form.reset();
        grupoIdInput.value = '';
        formTitle.textContent = 'Adicionar Novo Grupo';
        btnCancelar.classList.add('hidden');
    };

    // Função para carregar os grupos da API e preencher a tabela
    const carregarGrupos = async () => {
        try {
            const response = await fetch('/api/grupos-pagamento');
            if (!response.ok) throw new Error('Falha ao buscar dados.');
            const grupos = await response.json();

            tableBody.innerHTML = '';
            if (grupos.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="3" class="text-center">Nenhum grupo de pagamento encontrado.</td></tr>`;
                return;
            }

            grupos.forEach(grupo => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${grupo.nome}</td>
                    <td>${grupo.descricao || ''}</td>
                    <td class="action-buttons">
                        <button class="btn-action btn-delete" data-id="${grupo.id}">Excluir</button>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        } catch (error) {
            console.error('Erro ao carregar grupos:', error);
            // Adicionar uma notificação de erro para o usuário seria ideal aqui
        }
    };

    // Evento de submit do formulário para criar um novo grupo
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const nome = nomeInput.value.trim();
        const descricao = descricaoInput.value.trim();

        if (!nome) {
            alert('O nome do grupo é obrigatório.');
            return;
        }

        try {
            const response = await fetch('/api/grupos-pagamento', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nome, descricao })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.message || 'Erro ao salvar o grupo.');
            }

            alert(result.message); // Idealmente, usar um modal ou notificação
            resetForm();
            carregarGrupos();

        } catch (error) {
            console.error('Erro ao salvar:', error);
            alert(error.message);
        }
    });

    // Evento na tabela para lidar com cliques nos botões de ação (deleção)
    tableBody.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-delete')) {
            const grupoId = e.target.dataset.id;
            
            if (confirm('Tem certeza que deseja excluir este grupo? Esta ação não pode ser desfeita.')) {
                try {
                    const response = await fetch(`/api/grupos-pagamento/${grupoId}`, {
                        method: 'DELETE'
                    });
                    
                    const result = await response.json();

                    if (!response.ok) {
                        throw new Error(result.message || 'Erro ao excluir o grupo.');
                    }
                    
                    alert(result.message);
                    carregarGrupos();

                } catch (error) {
                    console.error('Erro ao excluir:', error);
                    alert(error.message);
                }
            }
        }
    });
    
    // Evento para o botão cancelar
    btnCancelar.addEventListener('click', resetForm);

    // Carrega os dados iniciais ao abrir a página
    carregarGrupos();
});
