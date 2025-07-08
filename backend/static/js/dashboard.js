document.addEventListener('DOMContentLoaded', () => {
    // Variáveis globais para gráficos e dados
    let yoyChart, ccProjectionChart, gpProjectionChart;
    let fullData = {};

    const formatCurrency = (value) => {
        if (typeof value !== 'number') value = parseFloat(value) || 0;
        return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
    };

    // Função para renderizar a tabela de lançamentos filtrados
    const renderFilteredTable = (lancamentos) => {
        const tableBody = document.getElementById('lancamentos-filtrados-tbody');
        tableBody.innerHTML = '';
        if (!lancamentos || lancamentos.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center">Nenhum lançamento encontrado para este filtro.</td></tr>';
            return;
        }
        lancamentos.forEach(l => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${l.data}</td>
                <td>${l.descricao}</td>
                <td>${l.centro_custo}</td>
                <td>${l.grupo_pagamento}</td>
                <td class="text-right">${formatCurrency(l.valor)}</td>
            `;
            tableBody.appendChild(row);
        });
    };
    
    // Função para buscar e renderizar os lançamentos da tabela
    const fetchAndRenderLancamentos = async () => {
        const type = document.getElementById('table-filter-type').value;
        const id = document.getElementById('table-filter-value').value;
        const periodEl = document.querySelector('.btn-period.active');
        const period = periodEl ? periodEl.dataset.period : '365';

        if (!id) {
            renderFilteredTable([]);
            return;
        }

        try {
            // A API agora recebe o período como um parâmetro de busca
            const response = await fetch(`/api/lancamentos_filtrados?type=${type}&id=${id}&period=${period}`);
            if (!response.ok) throw new Error('Falha ao buscar lançamentos');
            const data = await response.json();
            renderFilteredTable(data);
        } catch (error) {
            console.error("Erro ao buscar lançamentos:", error);
            const tableBody = document.getElementById('lancamentos-filtrados-tbody');
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center text-danger">Erro ao carregar dados.</td></tr>';
        }
    };

    // Atualiza o dropdown de valores para a tabela com base no tipo de filtro
    const updateTableFilterValues = () => {
        const filterType = document.getElementById('table-filter-type').value;
        const filterValueSelect = document.getElementById('table-filter-value');
        const items = fullData.filters[filterType === 'centro_custo' ? 'centros_custo' : 'grupos_pagamento'] || [];
        
        filterValueSelect.innerHTML = '<option value="">Selecione um item</option>';
        items.forEach(item => {
            const option = document.createElement('option');
            option.value = item.id;
            option.textContent = item.nome;
            filterValueSelect.appendChild(option);
        });
        renderFilteredTable([]); // Limpa a tabela ao trocar o tipo
    };

    // Função para atualizar os gráficos de projeção
    const updateProjectionChart = (chartInstance, data, selectedIds) => {
        if (!chartInstance) return;

        let dataToDisplay = data;
        if (selectedIds && selectedIds.length > 0) {
            dataToDisplay = data.filter(d => selectedIds.includes(String(d.category_id)));
        } else {
            const totalByCategory = data.reduce((acc, d) => {
                acc[d.category_id] = (acc[d.category_id] || 0) + parseFloat(d.value);
                return acc;
            }, {});
            const topCategoryIds = Object.entries(totalByCategory).sort(([,a],[,b]) => b-a).slice(0, 7).map(([id]) => id);
            dataToDisplay = data.filter(d => topCategoryIds.includes(String(d.category_id)));
        }

        const categories = [...new Set(dataToDisplay.map(d => d.category))];
        const datasets = categories.map(category => {
            const categoryData = dataToDisplay.filter(d => d.category === category);
            const color = `rgba(${Math.floor(Math.random() * 200)}, ${Math.floor(Math.random() * 200)}, ${Math.floor(Math.random() * 200)}, 0.8)`;
            return {
                label: category,
                data: fullData.projection_labels.map(month => {
                    const dataPoint = categoryData.find(d => d.label === month);
                    return dataPoint ? parseFloat(dataPoint.value) : 0;
                }),
                borderColor: color,
                backgroundColor: color,
                fill: false,
                tension: 0.1
            };
        });
        
        chartInstance.data.labels = fullData.projection_labels;
        chartInstance.data.datasets = datasets;
        chartInstance.update();
    };

    // Função principal para carregar o dashboard
    const loadDashboardData = async () => {
        try {
            const response = await fetch('/api/dashboard_data');
            if (!response.ok) throw new Error('Falha ao carregar dados do dashboard');
            fullData = await response.json();

            // 1. Atualizar Cards
            const cards = fullData.cards || {};
            document.getElementById('total-orcado-anual').textContent = formatCurrency(cards.total_orcado_anual);
            document.getElementById('total-realizado-anual').textContent = formatCurrency(cards.total_realizado_anual);
            const orcadoMes = parseFloat(cards.total_orcado || 0);
            const realizadoMes = parseFloat(cards.total_realizado || 0);
            const saldoMes = orcadoMes - realizadoMes;
            document.getElementById('total-orcado').textContent = formatCurrency(orcadoMes);
            document.getElementById('total-realizado').textContent = formatCurrency(realizadoMes);
            const saldoEl = document.getElementById('saldo');
            saldoEl.textContent = formatCurrency(saldoMes);
            saldoEl.classList.toggle('negativo', saldoMes < 0);

            // 2. Renderizar Gráfico de Comparativo Anual
            const yoyCtx = document.getElementById('yoyChart')?.getContext('2d');
            if (yoyCtx && fullData.yoy_data) {
                const monthLabels = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez'];
                if(yoyChart) yoyChart.destroy();
                yoyChart = new Chart(yoyCtx, {
                    type: 'bar',
                    data: {
                        labels: monthLabels,
                        datasets: [
                            { label: `Orçado ${fullData.yoy_data[0]?.ano_atual || new Date().getFullYear()}`, data: fullData.yoy_data.map(d => d.orcado_atual), backgroundColor: 'rgba(54, 162, 235, 0.5)' },
                            { label: `Realizado ${fullData.yoy_data[0]?.ano_atual || new Date().getFullYear()}`, data: fullData.yoy_data.map(d => d.realizado_atual), backgroundColor: 'rgba(255, 99, 132, 0.5)' },
                            { label: `Realizado ${fullData.yoy_data[0]?.ano_anterior || new Date().getFullYear() - 1}`, data: fullData.yoy_data.map(d => d.realizado_anterior), backgroundColor: 'rgba(75, 192, 192, 0.5)' }
                        ]
                    },
                    options: { scales: { y: { beginAtZero: true } } }
                });
            }

            // 3. Renderizar Gráficos de Projeção
            const ccCtx = document.getElementById('centroCustoChart')?.getContext('2d');
            if (ccCtx) {
                if(ccProjectionChart) ccProjectionChart.destroy();
                ccProjectionChart = new Chart(ccCtx, { type: 'line', data: { labels: [], datasets: [] } });
                updateProjectionChart(ccProjectionChart, fullData.cc_projection, []);
            }
            
            const gpCtx = document.getElementById('grupoPagamentoChart')?.getContext('2d');
            if (gpCtx) {
                if(gpProjectionChart) gpProjectionChart.destroy();
                gpProjectionChart = new Chart(gpCtx, { type: 'line', data: { labels: [], datasets: [] } });
                updateProjectionChart(gpProjectionChart, fullData.gp_projection, []);
            }

            // 4. Configurar Filtros
            const ccFilterSelect = document.getElementById('cc-filter-select');
            const gpFilterSelect = document.getElementById('gp-filter-select');
            const tableFilterType = document.getElementById('table-filter-type');
            const tableFilterValue = document.getElementById('table-filter-value');
            const periodButtons = document.querySelectorAll('.btn-period');
            
            if (fullData.filters) {
                // Popula filtros dos gráficos
                populateMultiSelect(ccFilterSelect, fullData.filters.centros_custo || []);
                populateMultiSelect(gpFilterSelect, fullData.filters.grupos_pagamento || []);
                // Popula filtro da tabela
                updateTableFilterValues();
            }

            // Adiciona Event Listeners
            ccFilterSelect.addEventListener('change', () => {
                const selectedIds = Array.from(ccFilterSelect.selectedOptions).map(opt => opt.value);
                updateProjectionChart(ccProjectionChart, fullData.cc_projection, selectedIds);
            });
            gpFilterSelect.addEventListener('change', () => {
                const selectedIds = Array.from(gpFilterSelect.selectedOptions).map(opt => opt.value);
                updateProjectionChart(gpProjectionChart, fullData.gp_projection, selectedIds);
            });
            tableFilterType.addEventListener('change', updateTableFilterValues);
            tableFilterValue.addEventListener('change', fetchAndRenderLancamentos);
            periodButtons.forEach(button => {
                button.addEventListener('click', () => {
                    periodButtons.forEach(btn => btn.classList.remove('active'));
                    button.classList.add('active');
                    fetchAndRenderLancamentos();
                });
            });

        } catch (error) {
            console.error("Erro no dashboard:", error);
        }
    };

    // Função para popular o select de filtros
    const populateMultiSelect = (selectElement, options) => {
        if (!selectElement) return;
        selectElement.innerHTML = '';
        options.forEach(option => {
            const opt = document.createElement('option');
            opt.value = option.id;
            opt.textContent = option.nome;
            selectElement.appendChild(opt);
        });
    };

    loadDashboardData();
});
e  