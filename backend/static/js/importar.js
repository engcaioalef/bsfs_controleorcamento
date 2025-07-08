document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('form-import');
    const statusContainer = document.getElementById('import-status');
    const logOutput = document.getElementById('log-output');
    const submitButton = form.querySelector('button[type="submit"]');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const formData = new FormData(form);
        const tipoArquivo = formData.get('tipo_arquivo');
        const arquivo = formData.get('arquivo');

        if (!tipoArquivo || !arquivo || arquivo.size === 0) {
            alert('Por favor, selecione o tipo de dados e um arquivo para importar.');
            return;
        }

        // Mostra o container de status e desabilita o botão
        statusContainer.style.display = 'block';
        logOutput.textContent = 'Enviando arquivo e iniciando processamento... Por favor, aguarde.';
        submitButton.disabled = true;
        submitButton.textContent = 'Importando...';

        try {
            const response = await fetch('/api/import', {
                method: 'POST',
                body: formData // FormData é enviado diretamente, sem headers 'Content-Type'
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.log || 'Ocorreu um erro desconhecido no servidor.');
            }

            // Exibe o log retornado pela API
            logOutput.textContent = result.log;

        } catch (error) {
            console.error('Erro na importação:', error);
            logOutput.textContent = `ERRO CRÍTICO: ${error.message}`;
        } finally {
            // Reabilita o botão ao final do processo
            submitButton.disabled = false;
            submitButton.textContent = 'Importar';
        }
    });
});
