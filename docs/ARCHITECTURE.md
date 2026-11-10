# Arquitetura

Pixel Recorder -> pasta acessível -> Syncthing (send-only) -> inbox (receive-only) -> ingestor -> arquivo imutável -> fila Redis -> worker -> transcrição -> análise -> PostgreSQL/pgvector -> API FastAPI -> PWA Next.js.

## Serviços
- **api**: autenticação, gravações, transcrições, busca, tarefas, associações.
- **worker**: ingestão, hash, transcrição, análise, embeddings e retentativas.
- **postgres/pgvector**: metadados, segmentos, resultados, vetores.
- **redis**: fila e jobs.
- **web**: biblioteca, player e revisão humana.
- **syncthing**: sincronização; validar caminho real exposto pelo Pixel.
- **calendar connector**: OAuth Google Calendar read-only; múltiplas contas.
- **location collector**: endpoint autenticado para amostras opt-in de localização.

## Dados essenciais
recordings(id, sha256, source, started_at, duration_ms, status, storage_path, privacy_mode)
segments(id, recording_id, start_ms, end_ms, speaker_id, text)
analyses(id, recording_id, model, prompt_version, summary, structured_json)
action_items(id, recording_id, description, owner_suggestion, due_at, evidence_segment_id, confirmed)
calendar_connections(id, account_label, encrypted_token_ref)
calendar_matches(id, recording_id, event_external_id, score, evidence_json, review_status)
location_samples(id, timestamp, latitude, longitude, accuracy_m, retention_until)
recording_locations(id, recording_id, location_sample_id, confidence, review_status)

## Proteções
Nunca commitar tokens OAuth, chaves de API, áudios, transcrições reais ou dados de localização. Criptografar tokens, limitar escopos, registrar consentimento para localização e permitir exclusão. Não expor banco, Redis ou administração Syncthing publicamente.

## Estratégia híbrida
Interfaces de provedores: TranscriptionProvider, AnalysisProvider, EmbeddingProvider. Implementações externas e locais intercambiáveis. Política por gravação: local-only, cloud-approved. Timeout, limite de custos, retentativas e rastreamento de versão do modelo.

## Implantação
Primeiro inventariar containers, portas, volumes, CPU/RAM e backups do WO4. Não executar docker compose up no host antes de revisão. Reservar RAM para os serviços atuais; modelos locais pesados apenas sob demanda.
