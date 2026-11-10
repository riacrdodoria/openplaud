# Google Recorder CLI — revisão técnica e integração

Revisão em 10/11/2026. O usuário escolheu explicitamente buscar o backup do Google Recorder na nuvem por CLI; sincronização direta do Pixel/Syncthing não é o fluxo escolhido. O receptor Syncthing criado durante a investigação foi parado e não houve pareamento com o telefone.

## Projetos revisados

| Projeto / revisão | Pontos úteis | Limites encontrados no código |
| --- | --- | --- |
| [CodefiLabs/google-recorder-cli](https://github.com/CodefiLabs/google-recorder-cli/tree/ab1a5c0c49deaf9de033abac1759df879d5b9ba4) — Python 0.3.0 | Perfil Chrome próprio, listagem/download, testes para transcrições longas, integração MCP opcional | Paginação ignorada; sync baixa tudo novamente; gravações com mesmo título podem sobrescrever arquivo; áudio inteiro carregado em RAM; data sem timezone; captura da maior resposta usa janela fixa de três segundos; dependências amplas; nenhum LICENSE nem licença em pyproject.toml/README na revisão consultada |
| [dylantmoore/google-recorder-cli](https://github.com/dylantmoore/google-recorder-cli/tree/3b6d0dcb4efc2929e58c0bc5111bf72fe9e65ae5) — TypeScript | HTTP direto após login; JSON/UUIDs; refresh de sessão; a README declara MIT | Não há arquivo LICENSE separado nem declaração de licença em package.json; paginação não completa; áudio em buffer sem limite; erros podem imprimir resposta do Google; configuração de API key exige passo adicional; possibilidade de perfil compartilhado e flags de ocultação de automação |

Nenhum é SDK oficial do Google Recorder. As CLIs gws/gog instaladas no WO4 não listam Google Recorder entre seus serviços; um recurso de gravação do Google Meet não representa o Gravador do Pixel. O backup do Gravador é disponibilizado em recorder.google.com, conforme a [documentação Google](https://support.google.com/pixelphone/answer/16267668?hl=pt-BR).

A abordagem é adequada como referência, mas nenhum dos dois foi adotado integralmente como sincronizador de produção. Não foram executados instaladores, MCP/skills ou rotinas de login desses repositórios. Não se pressupõe permissão de redistribuir código sem licença explícita. Os arquivos públicos foram lidos para identificar o protocolo e as limitações; a implementação integrada ao OpenPlaud é própria, sem incorporar arquivos desses projetos.

## Implementação preparada

`python -m openplaud.recorder_source` fornece login/status/sync. Um login inicial usa o Chrome instalado com perfil exclusivo em state/google-recorder/chrome-profile. O titular entra diretamente na página Google; não se solicita senha/cookie no chat. Não há leitura do navegador habitual, flags stealth ou --no-sandbox. CDP é temporário e vinculado ao loopback.

Após resposta válida de GetRecordingList, o conector guarda somente os dados de sessão necessários cifrados com Fernet, em arquivos privados fora do Git. A listagem/download periódicos usam HTTP para os endpoints Google, sem precisar manter Chrome, celular ou Mac abertos. Quando a sessão expira, AUTH_REQUIRED interrompe novas chamadas até novo login; não há promessa de sessão perpétua.

A sincronização tem ledger persistente por UUID, até cinco arquivos por execução, três tentativas por arquivo, limite de 100 MiB/download e validação de redirects. Nome de título não determina caminho de arquivo. Criação da gravação é UTC e vai ao contexto do OpenPlaud sem substituir notas ou data já revisada. Exclusões remotas nunca apagam a biblioteca local. Cinco falhas globais pausam o conector; erros não imprimem respostas Google ou credenciais. Um timer preparado agenda consultas de cinco em cinco minutos depois da autenticação.

O áudio é enviado apenas à API local/privada do próprio OpenPlaud, que deduplica por SHA-256 e aplica o pipeline existente. O conector inicial não importa transcrição Google para evitar tratar captions parciais como documento completo; o Whisper local continua sendo o provedor de transcrição validado.

## Limites explícitos

A primeira versão solicita até 100 registros recentes por consulta. Se o Google indicar cursor, o estado passa a PARTIAL_HISTORY: não se declara toda a biblioteca histórica importada. Paginação/backfill integral exigem validação do protocolo na conta real. O formato interno pode mudar. Não há OAuth oficial do Recorder integrado nem reaproveitamento presumido dos tokens gws/gog.

O login e o download de gravações reais ainda não foram executados. O estado observado é AUTH_REQUIRED com zero importações. Testes usam apenas fixtures sintéticas: timestamps UTC, UUIDs, títulos iguais, deduplicação do ledger, expiração, limites de tentativas, cifragem e bloqueio de redirects/targets indevidos. Isso não prova funcionamento na conta real.

## Autenticar no WO4

No terminal da sessão gráfica do WO4, dentro do checkout:

```sh
.venv/bin/pip install -r requirements-recorder.lock
.venv/bin/python -m openplaud.recorder_source login
.venv/bin/python -m openplaud.recorder_source status
.venv/bin/python -m openplaud.recorder_source sync
```

Chrome já está instalado. Playwright é opcional, usado apenas no login; os modelos de áudio não precisam dessas dependências. Faça login na mesma conta selecionada em Gravador → Backup e sincronização. O conector só considera login concluído depois de observar resposta válida do Recorder; uma pasta de perfil existente não é prova de autenticação.

Depois de validar pelo menos uma importação real, instale/adapte os templates openplaud-recorder.service/.timer para o checkout efetivo e habilite apenas o timer desse projeto. Eles ainda não foram habilitados. Não compartilhe perfil, auth.key ou auth.enc. Backups de credenciais devem ter proteção e chave separada.
