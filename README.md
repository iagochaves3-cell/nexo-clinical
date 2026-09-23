# Nexo Clinical Knowledge Platform 3.1

Substituição arquitetural do Nexo AI 2.x por uma plataforma de conhecimento clínico estruturado, versionado e auditável.

## Estado da implantação

Base técnica 3.1.0 recuperada do pacote preparado em 23/09/2026.
A API pública exige `NEXO_API_TOKEN` para todos os endpoints, exceto `/` e `/health`.
Gere um segredo aleatório URL-safe (32 a 256 caracteres) e configure-o apenas no servidor.
O Dockerfile inicia `python -m deploy.server` e inclui o diretório `deploy/`.

**Ainda não implementados:** pesquisa científica ao vivo, validação clínica completa,
migração dos demais plugins e integração verificada aos SitesGPTs.
`/v1/orchestrate` prepara o roteamento; não aprova prescrições.
Os testes de software não equivalem a validação científica de doses.

Os relatórios de preparação e seus hashes foram preservados como histórico.
Eles descrevem o estado anterior ao envio deste repositório; verifique o estado atual no Railway.

## Componentes entregues

- Source Registry versionado e validado por esquema.
- Knowledge Platform para recomendações computáveis e registros farmacológicos.
- Clinical Rules Engine determinístico.
- Núcleo de cálculos preservado da versão anterior.
- Roteamento para especialistas clínicos.
- Safety Pipeline com bloqueios críticos.
- Módulos multimodais iniciais: ECG, laboratório e imagem.
- API FastAPI, CLI, Dockerfile e suíte de testes.
- Evals locais com casos de segurança.

## Instalação

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[api,dev,multimodal]"
pytest
nexo-clinical health
python -m deploy.server
```

A API fica em `http://127.0.0.1:8000`; verifique `/health`.

## Limites clínicos

A plataforma é infraestrutura para suporte à decisão, não substitui validação clínica, protocolos institucionais ou regulamentação. O Source Registry inicial contém fontes estruturantes; diretrizes, protocolos e fármacos individuais devem ser ingeridos por domínio com revisão humana, versionamento e rastreabilidade.


## Incremento local de 23/09/2026 — não publicado

A branch `feat/live-evidence-pps-review` acrescenta busca bibliográfica real e
rascunho de revisão ancorado em resumos, sem aprovação clínica automática.
A produção permanece no commit base. Ver `docs/RETOMADA_2026-09-23.md` na raiz
do repositório para evidências, limites, credenciais e a restrição 403 do GitHub.
O trecho anterior descreve o pacote original e não comprova o estado publicado.
