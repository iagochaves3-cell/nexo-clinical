# Situação verificada em 23/09/2026

- Repositório: https://github.com/iagochaves3-cell/nexo-clinical
- Branch main observada: 94b1e19b920b7f2c6452ad85260cbdd6610b8876, apenas README.md.
- O proprietário possui permissões administrativas; a conexão do aplicativo recusou criação de blobs com HTTP 403, Resource not accessible by integration.
- Nenhum arquivo deste pacote foi enviado ao GitHub; nenhum novo deployment foi iniciado nesta tentativa.
- 41 testes passaram em Python 3.12; compilação sintática aprovada. Uma advertência de depreciação Starlette/httpx, sem falha.
- Testes técnicos não validam cientificamente doses/condutas.
- Dockerfile.railway, startCommand python -m deploy.server e healthcheck /health com timeout 120 s conferidos na configuração do serviço nexo-clinical-api. Há configuração staged anterior ainda pendente.
- O código inclui deploy/server.py e exige NEXO_API_TOKEN; não inclui segredo.
- Sem pesquisa científica ao vivo, sem aprovação clínica completa, sem migração dos demais plugins ou integração testada aos SitesGPTs.
- O domínio Railway existente não foi comprovado funcional nesta tentativa: a sonda HTTPS expirou. Isso não foi interpretado como diagnóstico de DNS.

## Retomada

A documentação oficial informa que o aplicativo GitHub no ChatGPT oferece leitura, e orienta usar Codex para gravar código: https://help.openai.com/en/articles/11145903-connecting-github-to-chatgpt . A integração desta sessão recusou a escrita, mesmo com ferramentas de escrita expostas. Reautorizar apenas leitura não resolve a gravação.

Usar uma conexão Codex autorizada para escrita neste repositório (Contents: read and write), ou enviar manualmente os arquivos descompactados da pasta nexo_clinical_platform pela interface autenticada do GitHub. Enviar o conteúdo para a raiz do repositório, não o ZIP nem a pasta como subdiretório. Preservar o histórico remoto. Depois vincular o serviço Railway existente à branch main e testar produção. Não criar outro serviço.

O arquivo FILE_SHA256.json e os relatórios antigos são evidências históricas do pacote de origem. CURRENT_FILE_SHA256.json descreve os arquivos atuais. O ZIP original da base e a wheel antiga foram preservados para rastreabilidade, mas não são os artefatos de implantação atuais.
