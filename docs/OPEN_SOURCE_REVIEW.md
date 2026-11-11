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

## Diarização local (10/11/2026)

- sherpa-onnx / sherpa-onnx-core 2.0.1: Apache-2.0, https://github.com/k2-fsa/sherpa-onnx/blob/master/LICENSE.
- Segmentação pyannote/segmentation-3.0: MIT, https://huggingface.co/pyannote/segmentation-3.0; conversão ONNX distribuída oficialmente em https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-segmentation-models. Não se usou token nem credencial Hugging Face. SHA-256 do ONNX: `220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079`.
- 3D-Speaker ERes2Net base 16k: projeto Apache-2.0 https://github.com/modelscope/3D-Speaker/blob/main/LICENSE, artefato ONNX oficial sherpa-onnx release `speaker-recongition-models`. SHA-256: `1a331345f04805badbb495c775a6ddffcdd1a732567d5ec8b3d5749e3c7a5e4b`.
- Artefatos e manifesto ficam fora do Git em state/models/diarization, montados somente para leitura. Manter os avisos upstream junto a qualquer redistribuição dos modelos. Não se publica um pacote com esses pesos nesta entrega.
