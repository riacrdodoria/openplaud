# OpenPlaud

MVP self-hosted para transformar áudios em transcrições, resumos e próximos passos. Desenvolvimento conduzido neste chat, diretamente no WO4; o executor autônomo de desenvolvimento foi descontinuado por decisão do usuário.

## O que está implementado

- Upload manual de WAV, MP3, M4A, Ogg, FLAC e WebM, até 100 MiB por arquivo; deduplicação SHA-256.
- Importação automática de uma pasta local, ignorando arquivos recentes/incompletos e links simbólicos. O fluxo real de exportação do Pixel precisa ser validado no aparelho.
- Worker persistente com estados, tentativas limitadas, recuperação de interrupções e preservação de resultados.
- Transcrição local PT/EN com faster-whisper small em CPU int8; modelo provisionado separadamente, sem download ou envio de áudio durante a execução.
- Resumos por Qwen2.5 1.5B local, decisões/tarefas com evidências e timestamps, fallback extrativo explícito. Responsáveis e prazos são informados/revisados pelo usuário.
- Biblioteca responsiva, player, destaque sincronizado da transcrição, busca por título/conteúdo e exportação TXT, JSON e VTT.
- Consulta em uma ou várias gravações com trechos citados. A consulta atual usa busca textual; não é chat generativo nem memória semântica.
- Importação de múltiplas agendas .ics; integração Google OAuth somente de leitura, com PKCE e tokens cifrados, pronta para configuração da conta. Associações são sugestões confirmáveis/rejeitáveis.
- Autenticação de usuário único, sessões HttpOnly, limites de entrada, backups verificáveis e acesso privado por Tailscale.

## Executar e verificar

Python 3.12, Linux, Docker/Compose. Leia [operação do MVP](docs/MVP_OPERATIONS.md) antes de iniciar no host. A configuração não reutiliza bancos, volumes ou redes de outros serviços.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/python -m unittest discover -s tests -v
node --check openplaud/web/app.js
```

Provisione o modelo público uma vez, com rede disponível:

```sh
.venv/bin/python -m openplaud.provision --model small --destination state/models/whisper-small
```

Prepare as pastas/segredos conforme o guia e use:

```sh
docker compose --env-file state/product-runtime.env -f compose.product.yml up -d
```

O produto usa a porta **8767**, vinculada somente ao endereço privado escolhido. O token e a chave de cifragem ficam em `state/product.env`, fora do Git. Não imprima `docker compose config` sem `--quiet`, pois o comando pode revelar segredos do env_file.

## Limites e escopo

SQLite e um worker único são a implementação inicial deliberada; PostgreSQL/Redis/Next.js permanecem evolução de arquitetura ([ADR](docs/adr/0002-interactive-mvp.md)). Não há inferência paga ou fallback para a nuvem. A transcrição automática pode errar e deve ser revisada. Áudios sem fala ou inválidos falham sem eliminar o original.

A análise local é limitada a oito blocos e oito minutos de geração por gravação; resumos parciais são sinalizados. Cada tentativa de processamento tem limite de 30 minutos; no máximo três tentativas. Não há garantia de tempo real nem validação de qualidade em reuniões reais longas. O worker pausa com menos de 2 GiB de disco livre.

OAuth real depende de credenciais e autorização do titular da agenda; nenhum acesso foi simulado como conectado. Pixel/Syncthing precisa de validação no aparelho. Diarização, reconhecimento de vozes, localização Android, integrações CRM, embeddings e chat generativo não fazem parte desta entrega. O manifesto permite modo standalone em contexto seguro; instalação PWA/HTTPS e QA visual mobile ainda precisam ser validados. Nenhum áudio privado é colocado em cache offline.

Veja [critérios e evidências](docs/MVP_ACCEPTANCE.md), [arquitetura](docs/ARCHITECTURE.md), [referências e licenças](docs/OPEN_SOURCE_REVIEW.md). A infraestrutura de controle de desenvolvimento anterior é histórica e não é necessária para usar o produto.
