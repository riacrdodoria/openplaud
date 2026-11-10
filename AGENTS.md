# Instruções para Codex

Leia docs/PRODUCT_BRIEF.md, docs/ARCHITECTURE.md e docs/OPEN_SOURCE_REVIEW.md antes de programar.

1. Comece por discovery e documentação de decisões (ADRs).
2. Implemente MVP incrementalmente com testes e migrations.
3. Não faça deploy no WO4 nem altere serviços existentes sem autorização explícita.
4. Não use APIs pagas sem aprovação; use mocks em testes.
5. Não coloque segredos, gravações, transcrições, localização ou dados pessoais no Git.
6. Prefira FastAPI + worker Python + PostgreSQL/pgvector + Redis + Next.js PWA.
7. Garanta processamento idempotente, políticas de privacidade e observabilidade.
8. Faça a integração do Pixel por pasta como hipótese a validar no dispositivo real.
9. Toda associação de calendário ou localização é sugestão revisável.
10. Documente comandos de instalação, rollback e backup.
