# Preparação do PPS — não publicada

Inspecionado em 23/09/2026: versão 230, commit
`95f3a4a9f0170ef7e55831f1388b60dad7275000`.
Projeto `appgprj_6a6e0d5a4ae881918e3fe01410787335`.

`worker/index.ts` é o servidor Cloudflare/Vinext existente. Não foi modificada
a receita nem o catálogo. `app/nexo-core.ts` permanece responsável pelas
conversões existentes. A regra documental está em
`references/nexo-clinical-global-2026-09-23/policy.md` no PPS.

## Entregue

- `nexo-server.mjs`: cliente exclusivamente de servidor com URL fixa HTTPS,
  segredo via `env.NEXO_INTEGRATION_TOKEN`, timeout, proibição de redirecionamento,
  contexto restrito e tratamento explícito de falha.
- `review-state.mjs`: invalidação imediata e descarte de respostas fora de ordem.
- Cinco testes executáveis com `node --test integrations/pps/nexo-server.test.mjs`.

Pesquisa ou rascunho jamais são convertidos em `VALIDADA`. Este incremento retorna
`resultadoValidacao: insuficiente` porque não realiza aprovação clínica integral.
Um resultado indisponível não libera medicamento, seleção ou exportação.

## Integração futura condicionada a teste real

1. Publicar os novos endpoints do NEXO após revisar o PR; configurar o token
   independente no servidor NEXO e como segredo no runtime Sites.
2. Testar busca e revisão com provedor configurado, inclusive falha de pesquisa,
   evidência insuficiente, contraindicações, apresentação, máximo e dose reversa.
3. Importar o cliente somente no Worker. A rota deve exigir identidade/autorização
   e limite de chamadas; nunca expor uma ponte pública irrestrita para um provedor pago.
   Não passar o token por React, `NEXT_PUBLIC_*`, `VITE_*`, URL ou armazenamento do navegador.
4. Construir `claims` a partir do conteúdo exato por medicamento; usar `claim_id`
   estável. Não enviar nome, nascimento, prontuário ou texto identificável.
   `deidentified: true` é uma obrigação do chamador, não uma anonimização automática.
5. Integrar os consumidores reais de `app/page.tsx`: seletores de terapêutica,
   `toggleReviewRow`, `prescriptionText`, `prescriptionExportBlocked`,
   `copyPrescription` e impressão. Alterar entrada invalida toda revisão anterior.
6. Fazer validação no servidor antes da saída final: hash recebido do navegador
   não é selo confiável. O hash NEXO vincula o rascunho ao payload, não o autoriza.
7. Somente após revisão clínica/farmacêutica/matemática e testes completos mapear
   para os cinco estados. Testar 2 meses/3 kg, 1 ano/10 kg, 4 anos/16 kg,
   mudanças durante a chamada, indisponibilidade, seleção, cópia e impressão.

O adaptador preparado não está importado no PPS nem altera sua publicação.
Não representa a integração funcional concluída.
