# Login com as mesmas credenciais do Sonhos

OpenPlaud aceita o usuário ricardo e a senha existente no Sonhos, por configuração explícita do proprietário. Sonhos utiliza HTTP Basic com segredo local, sem provedor OIDC/SSO. Não houve alteração naquele serviço.

Somente um verificador PBKDF2-HMAC-SHA256 (600 mil iterações, salt aleatório de 32 bytes) é provisionado em /state/login.json, modo 0600, do usuário do contêiner. A senha original é lida em memória durante a configuração, nunca impressa, gravada no OpenPlaud, enviada para API externa ou commitada. O caminho é configurado por OPENPLAUD_LOGIN_FILE; arquivo inválido impede inicialização.

O formulário envia usuário/senha ao endpoint de sessão do próprio OpenPlaud, que cria seu cookie host-only HttpOnly, SameSite Strict e Secure quando HTTPS. Não se compartilham cookies, bancos ou sessões com Sonhos. Em Tailscale a comunicação é privada; para o domínio público deve-se concluir o DNS e usar HTTPS. Nenhum segredo é colocado na URL ou armazenamento local do navegador.

Limite: dez tentativas em cinco minutos por endereço, no máximo duas verificações custosas simultâneas e 1024 endereços rastreados. A chave técnica Bearer continua disponível para o importador Google Recorder e como acesso alternativo. Credenciais Basic só são aceitas na abertura de sessão, não como acesso direto aos áudios.

Isto é reutilização das credenciais atuais, não SSO nem sincronização de mudanças de senha. Ao trocar a senha no Sonhos é necessário regenerar o verificador do OpenPlaud por procedimento local seguro. Não reutilizar a senha como token de API.

Rollback: retirar OPENPLAUD_LOGIN_FILE e restaurar a imagem anterior; a autenticação por chave continua válida. Preservar o arquivo de hash fora do Git. O serviço Sonhos permanece inalterado.
