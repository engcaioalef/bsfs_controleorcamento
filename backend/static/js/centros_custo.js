document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('form-centro-custo');
    const tableBody = document.getElementById('centros-custo-table-body');
    const formTitle = document.getElementById('form-title');
    const setorSelect = document.getElementById('setor_responsavel');
    const idInput = document.getElementById('centro-custo-id');
    const btnCancelar = document.getElementById('btn-cancelar');

    // Elementos do Modal
    const modal = document.getElementById('notification-modal');
    const modalMessage = document.getElementById('modal-message');
    const modalConfirmBtn = document.getElementById('modal-confirm-btn');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    let confirmAction = null;

    const showModal = (message, isConfirm = false) => {
        modalMessage.textContent = message;
        modalConfirmBtn.style.display = isConfirm ? 'inline-block' : 'none';
        modal.classList.remove('hidden');
    };

    const hideModal = () => {
        modal.classList.add('hidden');
        confirmAction = null;
    };

    modalCloseBtn.addEventListener('click', hideModal);
    modalConfirmBtn.addEventListener('click', () => {
        if (confirmAction) {
            confirmAction();
        }
        hideModal();
    });

    const resetForm = () => {
        form.reset();
        idInput.value = '';
        formTitle.textContent = 'Adicionar Novo Centro de Custo';
        btnCancelar.classList.add('hidden');
    };

    const carregarSetores = async () => {
        try {
            const response = await fetch('/api/setores');
            if (!response.ok) throw new Error('Falha ao buscar setores.');
            const setores = await response.json();
            setorSelect.innerHTML = '<option value="">Selecione um setor</option>';
            setores.forEach(setor => {
                const option = document.createElement('option');
                option.value = setor.id;
                option.textContent = setor.nome;
                setorSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Erro ao carregar setores:', error);
            setorSelect.innerHTML = '<option value="">Erro ao carregar setores</option>';
        }
    };

    const carregarCentrosCusto = async () => {
        try {
            const response = await fetch('/api/centros-custo');
            if (!response.ok) throw new Error('Falha ao buscar dados.');
            const centrosCusto = await response.json();
            tableBody.innerHTML = '';
            if (centrosCusto.length === 0) {
                tableBody.innerHTML = `<tr><td colspan="4" class="text-center">Nenhum centro de custo encontrado.</td></tr>`;
                return;
            }
            centrosCusto.forEach(cc => {
                const row = document.createElement('tr');
                row.dataset.cc = JSON.stringify(cc); // Armazena os dados na linha
                row.innerHTML = `
                    <td>${cc.nome}</td>
                    <td>${cc.codigo || 'N/A'}</td>
                    <td>${cc.setor_responsavel_nome}</td>
                    <td class="action-buttons">
                        <button class="btn-action btn-edit">Editar</button>
                        <button class="btn-action btn-delete">Excluir</button>
                    </td>
                `;
                tableBody.appendChild(row);
            });
        } catch (error) {
            console.error('Erro ao carregar centros de custo:', error);
        }
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const ccId = idInput.value;
        const url = ccId ? `/api/centros-custo/${ccId}` : '/api/centros-custo';
        const method = ccId ? 'PUT' : 'POST';

        const data = {
            nome: document.getElementById('nome').value.trim(),
            codigo: document.getElementById('codigo').value.trim(),
            setor_id: setorSelect.value,
            descricao: document.getElementById('descricao').value.trim()
        };

        if (!data.nome || !data.setor_id) {
            showModal('Nome e Setor Responsável são obrigatórios.');
            return;
        }

        try {
            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.message || 'Erro ao salvar.');
            showModal(result.message);
            resetForm();
            carregarCentrosCusto();
        } catch (error) {
            console.error('Erro ao salvar centro de custo:', error);
            showModal(error.message);
        }
    });

    tableBody.addEventListener('click', (e) => {
        const target = e.target;
        const row = target.closest('tr');
        if (!row) return;

        const ccData = JSON.parse(row.dataset.cc);

        if (target.classList.contains('btn-edit')) {
            formTitle.textContent = 'Editar Centro de Custo';
            idInput.value = ccData.id;
            document.getElementById('nome').value = ccData.nome;
            document.getElementById('codigo').value = ccData.codigo || '';
            document.getElementById('setor_responsavel').value = ccData.setor_responsavel_id;
            document.getElementById('descricao').value = ccData.descricao || '';
            btnCancelar.classList.remove('hidden');
            window.scrollTo(0, 0);
        }

        if (target.classList.contains('btn-delete')) {
            confirmAction = async () => {
                try {
                    const response = await fetch(`/api/centros-custo/${ccData.id}`, { method: 'DELETE' });
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.message);
                    showModal(result.message);
                    carregarCentrosCusto();
                } catch (error) {
                    console.error('Erro ao excluir:', error);
                    showModal(error.message);
                }
            };
            showModal('Tem certeza que deseja excluir este Centro de Custo?', true);
        }
    });

    btnCancelar.addEventListener('click', resetForm);

    carregarSetores();
    carregarCentrosCusto();
});
