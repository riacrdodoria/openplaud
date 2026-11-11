# Separação de falantes e chat local

## Estado e limites

Transcrição é conversão de fala em texto. Diarização estima quem falou quando, com rótulos anônimos por gravação. Não há cadastro biométrico nem reconhecimento de pessoas entre reuniões. Segmentos mistos/sobrepostos ou pouco cobertos ficam sem rótulo; os turnos originais continuam consultáveis e clicáveis. Não dividimos texto sem timestamps por palavra.

A diarização é um job próprio, separado do resumo; backfill não altera texto, resumos ou tarefas revisadas. Processamento local CPU, um job por vez, dois threads, limite de 30 minutos de áudio decodificado e 10 minutos de execução. Falha/timeout fica explícito e pode ser reenfileirado pelo botão. Jobs interrompidos tornam-se FAILED ao reiniciar; não há loop de tentativas. Modelos são montados read-only em /diarization, hashes verificados a cada execução. OPENPLAUD_DIARIZATION_MODELS habilita o worker; OPENPLAUD_DIARIZATION_ENABLED habilita o botão na API.

Validação: amostra real nova de um falante resultou em um; amostra oficial sherpa 0-four-speakers-zh.wav resultou em quatro com threshold 0.9. Com threshold 0.5 resultou em sete, e 0.7/0.8 em cinco. Não é benchmark de acurácia nem garantia em conversas brasileiras, ruído ou sobreposição. Precisa de revisão humana em conversa real com múltiplos participantes.

O chat permite todas, uma ou várias gravações. Usa FTS5 textual e amostra limitada, no máximo 20 gravações, 32 trechos/10 mil caracteres, com modelo Qwen local e timeout de 120s. Histórico contém até quatro perguntas e só existe na tela; ao sair/recarregar, é descartado. Não há embeddings/memória semântica longitudinal nesta implementação. Respostas incluem fontes verificadas quanto à existência e ao escopo, não garantia automática de implicação semântica. Se o modelo falhar, referências forem inválidas ou estiver ocupado, mostra trechos literais e aviso; pode abster-se por evidência insuficiente. Sem provedor externo/pago.

## Sincronização Google Recorder

Timer de usuário openplaud-recorder.timer habilitado, OnUnitInactiveSec=300, jitter até 20s. Independe do Mac e terminal; user lingering já habilitado no WO4. Sessão Google pode expirar; AUTH_REQUIRED interrompe importação até novo login manual. Limite de cinco áudios por execução e até 100 itens por página; truncamento sinalizado. No teste real, a quarta gravação nova foi importada, transcrita e resumida. Segredos de sessão continuam somente em state/google-recorder.

## Atualização e rollback

Antes do deploy, backup com `python -m openplaud.backup --root /state --dest /state/backups/DESTINO-NOVO` no container; isso verifica SQLite e checksums dos áudios. Imagem anterior preservada em openplaud-product:before-speakers-chat. Atualizar apenas api e worker com compose.product.yml e --no-deps; Ollama e outros serviços não precisam reiniciar.

Rollback: selecionar imagem anterior para api/worker e retirar as novas variáveis/mount de diarização da configuração. Não restaurar banco por cima de dados recentes nem remover tabelas. As tabelas novas são aditivas; o código antigo continua usando transcrição original e análises. Backups contêm dados privados e não devem ser publicados.
