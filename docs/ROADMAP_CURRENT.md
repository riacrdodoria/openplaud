# Roadmap verificado — 10/11/2026

## Incremento solicitado

1. Resumo da gravação nova: confrontado com a transcrição, cobertura dos dois assuntos, sem tarefas/decisões inventadas. Nome OpenPlaud transcrito incorretamente. Sem avaliação por escuta do áudio original.
2. Diarização: implementada e ativada no worker local; as quatro gravações reais importadas concluíram com um falante cada. Amostra oficial de quatro falantes resultou em quatro com threshold 0.9. Rótulos anônimos locais por gravação; trechos mistos permanecem sem atribuição. Botão, turnos clicáveis e exportação disponíveis. Pendente validar acurácia em reunião real multivoz.
3. Chat entre gravações: implementado com Qwen local, escopo múltiplo, histórico curto na tela, referências por gravação/segmento/timestamp e fallback explícito. Teste real de comparação de orçamento entre duas transcrições sintéticas e pergunta sem evidência. A falha inicial de resposta irrelevante motivou um filtro de correspondência e teste de regressão. Não há embeddings nem garantia de recall exaustivo.

## Base operacional

Google Recorder autenticado; importação periódica a cada cinco minutos, com jitter até 20s. Áudios e processamento no WO4. Upload manual, transcrição PT/EN, resumos, decisões/tarefas revisáveis, player, biblioteca, busca textual, exports, backup e recuperação implementados.

## Próximos incrementos

- Rever separação e resumos numa conversa real com dois ou mais participantes; melhorar alinhamento por palavras e permitir revisão/renomeação de falantes por gravação.
- Qualidade em reuniões longas: cobertura, alinhamento e avaliação comparativa com referências humanas.
- Embeddings locais e memória semântica longitudinal; consultas que encontrem conceitos com vocabulário diferente.
- Conectar e validar Google Calendar real, depois contexto de participantes/eventos com revisão.
- PWA HTTPS e QA visual/Android; localização opcional; n8n/Pipedrive conforme prioridades.
- Reconhecimento de identidade entre reuniões exige desenho e consentimento específicos; a diarização atual não faz isso.

## Pendência externa

Publicação no domínio conversas.ricardodoria.com.br: túnel preparado, falta CNAME na zona Cloudflare autorizada. Acesso privado Tailscale permanece disponível. A autorização de publicação existe; a credencial disponível não possui acesso DNS à zona necessária.
