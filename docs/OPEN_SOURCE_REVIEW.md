# Avaliação de componentes GitHub

Antes de copiar código, verificar licença atual, manutenção, dependências, segurança e compatibilidade:
- https://github.com/rishikanthc/Scriberr — referência de experiência de transcrição.
- https://github.com/skyhong2002/localplaud — referência de fluxo de trabalho estilo Plaud.
- https://github.com/m-bain/whisperX — alinhamento e diarização.
- https://github.com/SYSTRAN/faster-whisper — transcrição local.
- https://github.com/pyannote/pyannote-audio — diarização.
- https://github.com/syncthing/syncthing — sincronização.
- https://github.com/pgvector/pgvector — busca vetorial.

**Regra:** não importar código de aplicações inteiras sem auditoria da licença, compatibilidade e custo de manutenção. Bibliotecas consolidadas devem ser preferidas a reimplementações.

## Dependências efetivamente usadas no MVP

Sem copiar código de outras aplicações. Referências primárias consultadas:

- faster-whisper: https://github.com/SYSTRAN/faster-whisper — MIT; CTranslate2 MIT. Modelo local: https://huggingface.co/Systran/faster-whisper-small — MIT; revisão registrada junto ao modelo provisionado.
- PyAV: https://github.com/PyAV-Org/PyAV — BSD-3-Clause; FFmpeg e bibliotecas incorporadas têm seus próprios avisos. Dependência fixada em 15.1.0 após teste real de compatibilidade.
- Ollama: https://github.com/ollama/ollama — MIT, usando imagem oficial e digest fixado. Modelo https://ollama.com/library/qwen2.5:1.5b — Apache-2.0 conforme página do modelo. Distribuições binárias mantêm licenças de terceiros.
- icalendar: https://pypi.org/project/icalendar/ — BSD-2-Clause.
- FastAPI — MIT; cryptography — Apache-2.0/BSD-3-Clause. Dependências transitivas e versões em requirements.lock; não se declara aqui uma auditoria completa de vulnerabilidades/SBOM.

Falas sintéticas para validação foram geradas localmente com flite/eSpeak; ferramentas e áudios de teste permanecem fora do Git e não são necessários em runtime. Nenhuma gravação, transcrição ou dado de calendário de pessoas reais foi usado nos testes.
