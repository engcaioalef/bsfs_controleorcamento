document.addEventListener('DOMContentLoaded', () => {
    const tableBody = document.getElementById('lancamentos-table-body');

    // Função para formatar números como moeda brasileira
    const formatCurrency = (value) => {
        // Converte o valor para número, caso venha como string
        const numericValue = Number(value);
        if (isNaN(numericValue)) {
            return 'N/A';
        }
        return new Intl.NumberFormat('pt-BR', {
            style: 'currency',
            currency: 'BRL'
        }).format(numericValue);
    };

    // Função principal para carregar os lançamentos da API
    const carregarLancamentos = async () => {
        try {
            const response = await fetch('/api/lancamentos');
            if (!response.ok) {
                throw new Error('Falha ao buscar os dados dos lançamentos.');
            }
            const lancamentos = await response.json();

            // Limpa a tabela antes de adicionar os novos dados
            tableBody.innerHTML = '';

            if (lancamentos.length === 0) {
                // Mostra uma mensagem se não houver lançamentos
                const row = document.createElement('tr');
                row.innerHTML = `<td colspan="5" class="text-center">Nenhum lançamento encontrado.</td>`;
                tableBody.appendChild(row);
                return;
            }

            // Preenche a tabela com os dados recebidos
            lancamentos.forEach(lancamento => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${lancamento.data_lancamento_formatada}</td>
                    <td>${lancamento.descricao}</td>
                    <td>${lancamento.centro_custo}</td>
                    <td>${lancamento.grupo_pagamento}</td>
                    <td class="text-right">${formatCurrency(lancamento.valor)}</td>
                `;
                tableBody.appendChild(row);
            });

        } catch (error) {
            console.error('Erro ao carregar lançamentos:', error);
            tableBody.innerHTML = `<tr><td colspan="5" class="text-center error-message">Não foi possível carregar os dados.</td></tr>`;
        }
    };

    // Chama a função para carregar os dados assim que a página é aberta
    carregarLancamentos();
});
