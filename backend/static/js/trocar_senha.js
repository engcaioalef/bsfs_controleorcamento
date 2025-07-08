document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('form-trocar-senha');
    const errorMessageDiv = document.getElementById('error-message');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        errorMessageDiv.textContent = '';

        const senha_antiga = document.getElementById('senha_antiga').value;
        const nova_senha = document.getElementById('nova_senha').value;
        const confirmar_senha = document.getElementById('confirmar_senha').value;

        if (!senha_antiga || !nova_senha || !confirmar_senha) {
            errorMessageDiv.textContent = 'Todos os campos são obrigatórios.';
            return;
        }

        if (nova_senha !== confirmar_senha) {
            errorMessageDiv.textContent = 'A nova senha e a confirmação não correspondem.';
            return;
        }

        try {
            const response = await fetch('/api/trocar-senha', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    senha_antiga,
                    nova_senha,
                    confirmar_senha
                })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.message || 'Ocorreu um erro ao tentar alterar a senha.');
            }

            alert(result.message);
            // Redireciona para o dashboard após a troca bem-sucedida
            window.location.href = '/dashboard';

        } catch (error) {
            console.error('Erro ao trocar senha:', error);
            errorMessageDiv.textContent = error.message;
        }
    });
});
