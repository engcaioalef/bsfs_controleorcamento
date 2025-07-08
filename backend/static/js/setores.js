document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('form-setor');
    const tableBody = document.getElementById('setores-table-body');
    const formTitle = document.getElementById('form-title');
    const nomeInput = document.getElementById('nome');
    const setorIdInput = document.getElementById('setor-id');
    const btnCancelar = document.getElementById('btn-cancelar');

    // Função para limpar o formulário
    const resetForm = () => {
        form.reset();
        setorIdInput.value = '';
        formTitle.textContent = 'Adicionar Novo Setor';
        btnCancelar.classList.add('hidden');
    };

    // Função para carregar os setores da API e preencher a tabela
    const carregarSetores = async () => {
        try {
            const response = await fetch('/api/setores');
            if (!response.ok) throw new Error('Falha ao buscar dados dos setores.');
            const setores = await response.json();

            tableBody.innerHTML = '';
            if (setores.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="2" class="text-center">Nenhum setor encontrado.</td></tr>`;
                return;
            }

            setores.forEach(setor => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${setor.nome}</td>
                    <td class="action-buttons">
                        <button class="btn-action btn-delete" data-id="${setor.id}">Excluir</button>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        } catch (error) {
            console.error('Erro ao carregar setores:', error);
            tableBody.innerHTML = `<tr><td colspan="2" class="text-center error-message">Não foi possível carregar os dados.</td></tr>`;
        }
    };

    // Evento de submit do formulário para criar um novo setor
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const nome = nomeInput.value.trim();
        if (!nome) {
            alert('O nome do setor é obrigatório.');
            return;
        }

        try {
            // A rota para POST é a mesma de GET, mas o backend diferencia pelo método
            const response = await fetch('/api/setores', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nome })
            });

            const result = await response.json();
            if (!response.ok) throw new Error(result.message || 'Erro ao salvar o setor.');

            alert(result.message);
            resetForm();
            carregarSetores();

        } catch (error) {
            console.error('Erro ao salvar setor:', error);
            alert(error.message);
        }
    });

    // Evento na tabela para lidar com o botão de deletar
    tableBody.addEventListener('click', async (e) => {
        if (e.target.classList.contains('btn-delete')) {
            const setorId = e.target.dataset.id;
            
            if (confirm('Tem certeza que deseja excluir este setor? Esta ação não pode ser desfeita.')) {
                try {
                    const response = await fetch(`/api/setores/${setorId}`, {
                        method: 'DELETE'
                    });
                    
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.message);
                    
                    alert(result.message);
                    carregarSetores();

                } catch (error) {
                    console.error('Erro ao excluir setor:', error);
                    alert(error.message);
                }
            }
        }
    });
    
    // Evento para o botão cancelar
    btnCancelar.addEventListener('click', resetForm);

    // Carrega os dados iniciais ao abrir a página
    carregarSetores();
});
