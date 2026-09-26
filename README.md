# NEXO Clinical Knowledge Platform 3.1

Estado do código em main: busca bibliográfica Europe PMC/PubMed e rascunho de revisão autenticado implementados. A revisão não autoriza prescrição nem equivale a validação clínica. A versão de código não comprova o SHA em produção.

## Diretório canônico

A aplicação está em `NEXO_Clinical_3_1_Railway_Preparado_NAO_PUBLICADO_2026-09-23(1)/nexo_clinical_platform`.
As cópias soltas da raiz e os relatórios de preparação são históricos.
O build/instalação a partir da raiz do repositório não é suportado.

## Instalação e testes

A partir da raiz do repositório:

```bash
cd 'NEXO_Clinical_3_1_Railway_Preparado_NAO_PUBLICADO_2026-09-23(1)/nexo_clinical_platform'
```

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[api,dev]"
python -m pytest tests
python -m build --wheel
nexo-clinical health
```

O teste do adaptador JavaScript é executado na raiz do repositório:
`node --test integrations/pps/nexo-server.test.mjs`.

## Inicialização protegida

Configure `NEXO_API_TOKEN` no ambiente do servidor: segredo URL-safe aleatório de
32–256 caracteres. Não o coloque em commits, frontend, URLs ou saídas de teste.

Na pasta canônica, use `python -m deploy.server` ou `nexo-clinical-api`.
Para ASGI, use `uvicorn deploy.server:create_app --factory`.
O console e `main.py` com `PORT` delegam à entrada protegida.
A fábrica `nexo_clinical.api.create_app` é interna; não deve ser usada para servir
a aplicação diretamente. Não há instância pública `nexo_clinical.api:app`.
O servidor falha antes de escutar se o token estiver ausente/inválido.

Dockerfile e Dockerfile.railway da pasta canônica usam `python -m deploy.server`.
Root Directory do serviço:
`/NEXO_Clinical_3_1_Railway_Preparado_NAO_PUBLICADO_2026-09-23(1)/nexo_clinical_platform`.
Porta: `PORT`, padrão 8000. Esta documentação não aplica configurações nem
confirma uma implantação Railway.

## Contratos HTTP

| Método | Caminho | Acesso / função |
|---|---|---|
| GET | /, /health | Público; identificação/saúde técnica |
| GET | /v1/capabilities | Token principal ou de integração |
| GET | /v1/sources | Token principal; registros de fontes |
| POST | /v1/orchestrate | Token principal; roteamento de especialistas |
| POST | /v1/safety/review | Token principal; regras técnicas de segurança |
| POST | /v1/multimodal/ecg/assess | Token principal; metadados ECG |
| GET | /v1/multimodal/ecg/qtc | Token principal; qt_ms e rr_ms positivos/finitos |
| POST | /v1/multimodal/laboratory/analyze | Token principal; cálculos derivados |
| POST | /v1/multimodal/imaging/assess | Token principal; metadados de imagem |
| POST | /v1/evidence/search | Token principal ou de integração; pesquisa bibliográfica |
| POST | /v1/clinical/review | Token principal ou de integração; rascunho com referências |
| GET | /docs, /redoc, /openapi.json | Token principal |

O token opcional `NEXO_INTEGRATION_TOKEN` deve ser diferente do principal e
só acessa capabilities, pesquisa e revisão. Configure o provedor de revisão
somente com `NEXO_REVIEW_API_KEY` e `NEXO_REVIEW_MODEL` no ambiente.
Sem provedor, a revisão retorna `review_unavailable`; sem resumo utilizável,
`insufficient_evidence`. Pesquisa externa indisponível retorna 503.
Corpos upstream malformados/truncados geram erros sanitizados, sem copiar seu conteúdo.

Laboratório aceita os campos numéricos estritos e finitos `na`, `cl`, `hco3`,
`k`, `glucose_mg_dl`, `bun_mg_dl`. Campo ausente/null permanece desconhecido;
não é substituído por zero. Strings/booleanos/não finitos são rejeitados com 422.
Não há faixas clínicas novas nesta validação.

ECG aceita formato `digital_signal`, `pdf_vector` ou `image`;
`lead_count` é inteiro positivo, `speed_mm_s` e `gain_mm_mv` são números
positivos e finitos. Ausência de metadados mantém `quality=insufficient`;
dados inválidos retornam 422. Não foi imposto teto clínico.

Safety aceita `text` string, `context` objeto e `citations` lista de strings/objetos.
Em context, peso deve ser positivo/finito e input_quality deve ser string;
os demais campos de contexto são preservados. Essa validação estrutural não
confere a qualidade clínica das citações.

O cálculo ponderal de quantidade aceita unidades sem tempo, como mg/kg.
Unidades como mg/kg/h, mg/kg/dia e mg/kg/min são rejeitadas nessa função;
conversões de taxa pertencem às funções próprias. Fórmulas e limites clínicos
não foram alterados.

## Limites e histórico

As suítes usam entradas sintéticas/mocks. Testes e /health não validam doses,
indicações, apresentações, prescrições, migração funcional ou integração com Sites.
A API de roteamento não aprova tratamentos; revisão mantém
`clinical_validated=false` e `prescribing_authorization=false`.

A integração foi mesclada em main em 23/09/2026. Os documentos de preparação
e RETOMADA_2026-09-23 descrevem aquele momento e seus bloqueios de publicação;
não representam o estado atual do GitHub nem garantem o estado do Railway.
A auditoria corretiva de 26/09/2026 preserva o motor e os documentos originais.
