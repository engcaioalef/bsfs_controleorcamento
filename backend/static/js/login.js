document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const errorMessageDiv = document.getElementById('error-message');

    // Verifica se o formulário existe na página antes de adicionar o listener
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault(); // Impede o envio padrão do formulário que expõe a senha
            errorMessageDiv.textContent = ''; // Limpa mensagens de erro anteriores

            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;

            try {
                // Envia os dados para a API usando o método POST e corpo JSON
                const response = await fetch('/api/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email, password }),
                });

                const result = await response.json();

                if (response.ok) {
                    // Se o login for bem-sucedido, redireciona para o dashboard
                    window.location.href = '/dashboard';
                } else {
                    // Se houver erro, exibe a mensagem retornada pela API
                    errorMessageDiv.textContent = result.message || 'Erro ao tentar fazer login.';
                }
            } catch (error) {
                console.error('Erro na requisição de login:', error);
                errorMessageDiv.textContent = 'Não foi possível conectar ao servidor. Tente novamente mais tarde.';
            }
        });
    }
});
