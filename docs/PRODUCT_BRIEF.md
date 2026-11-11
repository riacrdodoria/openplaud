# OpenPlaud — Product Brief

## Objetivo
Plataforma self-hosted de inteligência de áudio para importar gravações do Google Pixel Recorder e produzir transcrições, diarização, resumos, decisões, tarefas e memória pesquisável.

## Ambiente alvo
Trycoo WO4, Ryzen 9 6900HX, 16 GB RAM, SSD 512 GB, Ubuntu 24.04, Docker e Tailscale. Reutilizar serviços existentes somente após inventário não destrutivo.

## MVP
1. Importação manual e sincronização pela nuvem Google Recorder (CLI no WO4); pasta observada permanece alternativa, sem Syncthing ativo.
2. Deduplicação SHA-256, armazenamento local e fila de processamento.
3. Transcrição híbrida: provedor externo opcional ou faster-whisper local.
4. Resumos e extração estruturada de decisões e tarefas, sempre com evidências/timestamps.
5. Biblioteca, player, transcrição, busca e interface responsiva.
6. Associação sugerida com eventos Google Calendar por OAuth read-only.
7. Localização opcional via coletor Android, nunca exigida para processamento.

## Fases posteriores
Diarização local anônima e chat local com citações entre gravações foram implementados incrementalmente; critérios e limitações em SPEAKERS_CHAT_OPERATIONS.md. Reconhecimento de vozes com consentimento, memória semântica, integrações n8n/Pipedrive e múltiplos usuários permanecem posteriores.

## Requisitos não funcionais
Privacidade por padrão; controle por gravação sobre envio a APIs externas; autenticação; backups; retenção configurável; observabilidade; testes; execução sem GPU; acesso privado por Tailscale.

## Critérios de aceite MVP
- Importação idempotente de arquivos de áudio.
- Pipeline assíncrono com estados e reprocessamento.
- Resumo e tarefas armazenados com referência aos segmentos.
- Falha de provedor não elimina áudio nem transcrição.
- Nenhum áudio enviado externamente sem política/autorização aplicável.
- Associação de calendário corrigível e não tratada como fato.
- Deploy não interfere nos serviços existentes do host.
