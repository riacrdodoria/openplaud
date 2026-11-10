# conversas.ricardodoria.com.br

O usuário autorizou explicitamente a publicação da interface do OpenPlaud na internet via Cloudflare em 10/11/2026, mantendo a chave de acesso. Essa autorização foi solicitada após a revisão automática rejeitar uma ativação inicial por falta de consentimento específico sobre a biblioteca privada. Após o consentimento, a ativação do serviço exclusivo foi permitida.

## Preparado

- Túnel exclusivo openplaud-conversas; ID 5cba033e-d275-4322-863c-d6041110792d.
- Credenciais e configuração somente em state/domain, fora do Git, modo privado.
- Serviço de usuário openplaud-domain.service ativo/habilitado; linger já estava habilitado.
- Origem privada: API no IP Tailscale do host, porta 8767. Nenhuma porta pública foi aberta no host.
- Host permitido explicitamente, redirecionamento HTTPS para esse hostname, cookies Secure e HSTS, confiança em cabeçalhos de proxy limitada aos saltos locais definidos.
- Painéis administrativos do desenvolvimento e Syncthing não são rotas deste túnel.

## Bloqueio externo real

A criação automática do DNS falhou com Cloudflare código 10000 (Authentication error). O certificado antigo permite administrar túneis da conta, mas não possui acesso válido à zona ricardodoria.com.br. Outros certificados existentes foram consultados somente para leitura e pertencem a outras zonas; não foram modificados ou usados para criar DNS em zonas diferentes.

Nenhum registro foi sobrescrito. Não se declara o domínio publicado/HTTPS público validado até o DNS correto existir. É necessário renovar a autenticação da zona correta ou o titular criar no Cloudflare:

- Tipo: CNAME
- Nome: conversas
- Destino: 5cba033e-d275-4322-863c-d6041110792d.cfargotunnel.com
- Proxy: ativado
- TTL: automático

Depois, verificar HTTPS com certificado válido, GET anônimo de /api/recordings retornando 401, login com cookie Secure, áudio Range autorizado e Cache-Control no-store. A chave do aplicativo permanece a mesma; não é incluída nesta documentação.

## Rollback

Parar/desabilitar somente openplaud-domain.service. Reverter apenas o registro conversas se criado para este túnel e restaurar as variáveis de runtime anteriores da API, preservando dados. Não modificar outros túneis, serviços, firewall ou Tailscale.
