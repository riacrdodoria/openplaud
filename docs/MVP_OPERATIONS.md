# Operação do MVP local

## Preparação

Este guia substitui as instruções do executor de desenvolvimento para o uso do produto. O trabalho de código é feito no chat; apenas o processamento de áudio roda em segundo plano.

1. Verifique recursos e portas sem alterar serviços existentes. Reserve a porta 8767 somente em loopback ou no IP Tailscale do WO4. Nunca use wildcard no lado do host, Funnel ou exposição pública.
2. Instale as dependências em .venv usando requirements.lock e provisione faster-whisper small com `python -m openplaud.provision`. O arquivo openplaud-model.json registra a revisão do modelo. PyAV 15.1.0 está fixado porque a versão 19 removeu uma interface utilizada por faster-whisper 1.2.1.
3. Crie state/product, state/inbox e state/ollama. O diretório de dados deve ter modo 0700 e pertencer ao UID/GID 10001 dos contêineres. Inbox precisa apenas ser legível pelo worker; o worker nunca apaga nem altera os originais da pasta.
4. Gere um token aleatório de pelo menos 32 caracteres e uma chave Fernet. Grave `OPENPLAUD_API_TOKEN` e `OPENPLAUD_TOKEN_KEY` em state/product.env, modo 0600, sem Git. A chave de cifragem deve ser guardada em backup seguro separado do banco.
5. Em state/product-runtime.env, informe `OPENPLAUD_BIND_IP` como loopback ou IP Tailscale específico. Fixe `OPENPLAUD_OLLAMA_IMAGE` no digest da imagem validada.
6. Provisione qwen2.5:1.5b na pasta state/ollama usando um contêiner temporário sem portas, com memória/CPU limitadas e somente esse diretório montado. Encerre-o após `ollama pull`. O Ollama de runtime fica somente na rede interna, sem saída à internet.
7. Construa Dockerfile.product, valide Compose com `config --quiet`, rode os testes e então inicie somente o projeto compose.product.yml.

## Serviços e limites

- API: porta 8767 privada, 384 MiB RAM, 0,5 CPU. Sem access log para evitar registrar nomes de arquivos/códigos OAuth. Sessões HttpOnly/SameSite Strict duram oito horas; o token não fica em localStorage. Reiniciar a API encerra sessões, sem perder dados.
- Worker: um único processo supervisor com lock, 2 GiB RAM, duas CPUs; transcrição int8 em subprocesso. Encerra processo de tarefa em 30 minutos; três tentativas no máximo, com retomada de interrupções. A repetição de tarefa FAILED é manual; não há loop infinito de retries.
- Ollama: 2 GiB RAM, duas CPUs, uma geração por vez; descarrega o modelo ao terminar. Sem porta publicada e sem acesso a redes externas. Dependendo da gravação, o worker usa fallback extrativo explícito.
- Filesystems dos contêineres somente de leitura, sem capacidades, sem escalada de privilégios, sem socket Docker ou credenciais do host. Apenas dados próprios montados. Docker logs rotacionam 2 × 5 MiB.
- A API tem uma rede adicional para OAuth Google; o código não usa essa rede para enviar áudios ou transcrições. O worker e Ollama usam somente a rede interna.

A capacidade de CPU/RAM deve ser acompanhada ao usar reuniões reais longas. Um arquivo de até 100 MiB ainda pode ter muitas horas; o tamanho permitido não garante conclusão dentro de 30 minutos. A biblioteca não tem exclusão automática, quota rígida total ou política de retenção nesta versão: acompanhe disco, use backups e não exponha o serviço ao público.

## Pixel e pasta

Aponte a sincronização que você escolher para state/inbox e valide no Pixel se o Recorder realmente permite exportar para essa pasta. O watcher aguarda 15 segundos sem mudança de tamanho/mtime, copia com limite de 100 MiB, rejeita links e verifica novamente antes de importar. Conteúdo idêntico produz uma única gravação. Arquivos de pasta inválidos não devem impedir os próximos. Marque a gravação com data/hora real na interface para contextualizar a agenda; a data de upload não é tratada como data da reunião.

A pasta local foi testada; sincronização no telefone não foi configurada ou atestada. O worker não acessa o sandbox privado do Recorder.

## Google Calendar

Crie um cliente OAuth Web no seu projeto Google, habilite Calendar API e configure a URL exata `/oauth/google/callback`. Use HTTPS ou localhost HTTP através de encaminhamento autorizado. Google normalmente não aceita um IP Tailscale HTTP como callback Web; não altere Tailscale/HTTPS do host sem revisão.

Adicione a state/product.env: OPENPLAUD_GOOGLE_CLIENT_ID, OPENPLAUD_GOOGLE_CLIENT_SECRET e OPENPLAUD_GOOGLE_REDIRECT_URI. Preserve OPENPLAUD_TOKEN_KEY entre reinícios. Recrie somente a API para carregar a configuração. Na interface, conecte cada conta e solicite sincronização; o escopo é calendar.events.readonly. A agenda principal é consultada de 30 dias atrás a 30 dias à frente, com no máximo 2.500 eventos por sincronização. Refresh token é cifrado no banco. Erros de autorização pedem reconexão, sem mostrar tokens.

A sincronização Google é manual nesta versão. Eventos recorrentes são expandidos pela API Google. Importação .ics é alternativa local; ignora eventos recorrentes não expandidos, de dia inteiro ou sem fuso. Apenas o horário fornecido pelo usuário cria sugestões temporais. Confirmar/rejeitar é explícito; participantes não são presumidos como vozes reconhecidas.

## Backup e restauração

Use `python -m openplaud.backup --root /state --dest /state/backups/IDENTIFICADOR_NOVO` dentro do contêiner do produto. O destino deve ser novo: nenhuma pasta existente é sobrescrita. O snapshot SQLite inclui transcrições, análises e tokens cifrados; copia apenas objetos de áudio referenciados no snapshot e verifica SHA-256. Não inclui token de acesso/chave Fernet nem modelos públicos. Trate o backup como dado privado e cifre armazenamento fora do host.

Verifique com `python -m openplaud.backup --dest CAMINHO --verify`. Para restaurar, pare apenas API/worker do OpenPlaud, copie o snapshot validado para um diretório vazio, restaure a chave de configuração separadamente e monte esse diretório. Mantenha o original preservado até conferir o resultado. Nenhuma migração destrutiva existe nesta versão; as tabelas adicionais são criadas sem remover gravações antigas.

## Rollback

Pare apenas os serviços do Compose OpenPlaud. Preserve state/product, state/inbox e segredos. Reponha a imagem/versionamento anterior e seu snapshot de dados compatível; verifique integridade antes de reiniciar. Não execute docker prune nem remova volumes de outros projetos. O antigo controle de desenvolvimento pode ficar parado com seu estado preservado.

## Validação ainda necessária no uso real

Reunião real do titular, ruído/qualidade em português, gravações longas, navegador Android, instalação em contexto HTTPS, exportação/sincronização no Pixel e consentimento Google real. Os testes automatizados e amostras sintéticas não equivalem a esses testes de aceitação em dispositivo/conta reais.

Ollama também usa `OLLAMA_NO_CLOUD=1`, conforme https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features . A rede interna permanece uma barreira adicional. A geração pode aguardar até 180 segundos por chamada para o primeiro carregamento; o orçamento total local de análise continua 480 segundos e o resumo parcial é sinalizado se o orçamento acabar. Não há fallback para modelos pagos.

A proteção de Host usa OPENPLAUD_ALLOWED_HOSTS. Se configurar um domínio HTTPS para OAuth, adicione explicitamente esse nome à lista permitida da API; não use `*`. O callback OAuth aceita navegação entre sites somente na rota dedicada, que valida state/PKCE de uso único; as demais rotas mantêm proteção de origem.
