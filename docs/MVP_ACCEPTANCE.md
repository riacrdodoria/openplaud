# MVP — critérios de aceite e limites

Desenvolvimento interativo no WO4 em 10/11/2026. Não inclui conclusão de todo o roadmap original.

| Critério do produto | Implementação / evidência | Limite |
| --- | --- | --- |
| Importação idempotente | Upload autenticado, SHA-256 e um job por objeto; teste de deduplicação e concorrência | 100 MiB/arquivo; não há quota total rígida |
| Pasta sincronizada | Watcher espera estabilidade, rejeita symlinks e limita cópia; teste de pasta e duplicação | Exportação/Syncthing no Pixel real ainda não validada |
| Pipeline assíncrono e retomada | SQLite transacional, lock único, subprocesso limitado, estados, recuperação e três tentativas | Retry de FAILED é manual; timeout de 30 minutos |
| Transcrição PT/EN | Whisper small int8 em CPU, modelo com revisão fixada; falas sintéticas PT e EN transcritas localmente | Não é avaliação de acurácia em reuniões humanas longas/ruidosas |
| Resumos / decisões / tarefas | Qwen2.5 local, JSON schema, citações validadas; fallback literal explícito, revisão e responsável/prazo manual | IA pode errar; oito blocos/480 segundos de análise; cobertura parcial sinalizada |
| Player / biblioteca | Sessão HttpOnly, Range, transcrição por timestamps, realce, busca e exportações TXT/JSON/VTT | QA visual/Android ainda pendente |
| Preservação em falha | Resultados de transcrição gravados antes da análise; retry reutiliza texto salvo; áudios imutáveis | Versões históricas de resumos editados ainda não existem |
| Privacidade | Providers verificam política antes de chamada; runtime de áudio/modelo em rede interna; Ollama cloud desabilitado | OAuth Calendar é um fluxo externo explícito, sem envio de áudio |
| Agenda revisável | Importação ICS e matches temporais; confirmação/rejeição persistida e testada; OAuth read-only com PKCE e tokens cifrados | OAuth real exige cliente Google e consentimento; sincronização é manual |
| Backup | Snapshot SQLite e cópia de objetos referenciados, verificação de checksum e teste de corrupção/restauração | Chave de cifragem deve ter backup separado |
| Isolamento do host | Novos contêineres não-root, limites, filesystem read-only, volumes próprios, porta privada | Não equivale a auditoria de produção multiusuário |

## Verificações realizadas

Testes unitários/de integração abrangem autenticação, sessão, logout, Range, upload, busca, citações, exports, edição de tarefas, retomada, concorrência, limites JSON/chunked, schema existente, backup, OAuth/PKCE/criptografia e state de uso único, hosts permitidos e retorno OAuth entre sites.

Amostras sintéticas foram geradas no WO4 em português e inglês, sem usar gravações pessoais ou IA paga. O modelo base inicialmente não transcreveu adequadamente a voz sintética em português; o small transcreveu ambas as amostras corretamente. PyAV foi fixado após encontrar incompatibilidade real da versão 19 com faster-whisper.

O primeiro teste HTTP completo no serviço privado processou PT e EN, produziu transcrição, decisões e tarefas, e validou autenticação, reprodução parcial, VTT e recuperação de trechos. Nesse teste a análise usou fallback extrativo; isso foi informado no resultado. A geração local foi então endurecida com JSON schema para evitar respostas vazias/sem citações.

A interface não foi inspecionada em navegador automatizado porque não havia runtime de browser QA disponível. Não foi feito reboot do Ubuntu, alteração de firewall, SSH ou Tailscale, uso de gravações reais, autorização Google real ou configuração no Pixel. Nenhum desses itens é declarado validado.

## Fora desta entrega

Diarização/biometria de voz, localização Android, integrações CRM, embeddings/pgvector, memória semântica longitudinal, chat generativo, autenticação multiusuário, implantação pública, cache offline de dados privados e instalabilidade PWA em HTTPS. O módulo de consulta atual recupera citações por busca textual, sem gerar respostas factuais sem evidência.

## Resultado final no WO4

- **39 testes automatizados aprovados**, além de sintaxe JavaScript, compilação Python e `pip check`.
- Validação HTTP ponta a ponta em contêineres com amostras sintéticas PT e EN: upload → fila → transcrição real → análise → player/Range → exportação VTT → consulta com citações.
- A última amostra em português concluiu com `analysis.method=ollama-local`, resumo factual específico da amostra, uma decisão e uma tarefa. A saída foi obtida do Qwen local, sem provider externo. Amostras anteriores com fallback foram preservadas e mantêm essa informação explícita.
- Backup real criado em diretório próprio novo e verificado por checksum: quatro objetos sintéticos. Testes automatizados também verificaram abertura da cópia restaurada e detecção de corrupção.
- API e worker reiniciados: quatro gravações continuaram DONE; transcrição e análise local validada permaneceram idênticas. Sessões de navegador são encerradas por reinício da API, conforme projeto.
- API healthy na porta privada 8767; worker e Ollama sem portas publicadas. Os três contêineres usam UID 10001, filesystem read-only e restart unless-stopped.
- Uso observado em repouso: API ~45 MiB, worker ~16 MiB e Ollama ~21 MiB após descarregar o modelo. São medições de repouso, não limites de pico. Limites configurados: 384 MiB/2 GiB/2 GiB.
- O observador/autocoder anterior foi parado, com estado preservado. Nenhum serviço alheio foi reiniciado.
- Disco na verificação final: cerca de 131 GiB livres, 68% ocupado; o bloqueio de capacidade inicial não persistia nessa medição. Não foi feita limpeza de dados existentes por esta implementação.

Ainda não há autorização Google real, validação no telefone, QA visual de navegador ou teste de reboot do host. Esses resultados não são inferidos dos testes HTTP ou de mocks.
