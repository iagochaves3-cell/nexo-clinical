# NEXO — preparação atualizada; publicação global NÃO concluída

Data: 23/09/2026. Este pacote é um piloto técnico local. Não comprova migração dos plugins nem integração aos SitesGPTs/Mesclar.

## Estado observado no Railway
Projeto `857761d9-fe68-4a76-8114-cab1346778d1`; ambiente `b46acc9a-5c76-4c7b-926e-12387a66fe2f`; serviço `8aabd13f-b848-47ca-bd07-4588e7aaee3e`.
Domínio registrado: https://nexo-clinical-api-production.up.railway.app
A implantação `45fd3e25-94c1-4f1a-9856-9274fe578474` exibe SUCCESS, mas os logs contêm `ModuleNotFoundError: No module named 'deploy'`; a inspeção retornou zero réplicas em execução e uma encerrada com falha.
PORT, NEXO_API_TOKEN e variáveis de Python foram configurados pelo conector, sem divulgar seus valores neste pacote. O segredo não está nos arquivos.
A correção de healthcheck `/health`, timeout de 120 segundos e ON_FAILURE/3 está STAGED, não ativada. Não houve parada/remoção do deployment defeituoso: essa ação não foi disponibilizada pelas ferramentas usadas.
Os testes externos não foram conclusivos: a ferramenta web não acessou as URLs, o contêiner local não resolveu DNS e a sonda externa foi abortada. Isso não foi tratado como prova de falha de DNS do domínio.

## Código preservado e corrigido
Base: `nexo_clinical_platform-3.1.0-pediatric-governance.zip`, encontrada na Biblioteca; original íntegro em `source_baseline/`.
A base identifica o projeto como 3.1.0 no pyproject, mas o módulo e a API ainda anunciavam 3.0.0. Corrigida somente essa inconsistência de versão.
O adaptador de autenticação e seus testes foram reaproveitados do pacote 3.0 previamente preparado. O Dockerfile padrão e Dockerfile.railway agora iniciam `python -m deploy.server`, com usuário não-root.
Não foram alteradas doses, esquemas ou regras de farmacoterapia. Os testes são testes de software, não validação científica.
`/v1/orchestrate` continua apenas preparando roteamento de especialistas; a pesquisa científica ao vivo e o filtro clínico completo NÃO estão implementados.

## Publicação do piloto — somente por canal autenticado de envio de código
A conexão do aplicativo Railway já funciona. Falta o canal de upload do diretório local: a CLI deste ambiente não está instalada/autenticada e não há ação de upload local no conector usado.
A partir da raiz desta pasta, em um terminal com Railway CLI autenticada na conta do proprietário, o comando para o serviço EXISTENTE é:

```sh
railway up --project 857761d9-fe68-4a76-8114-cab1346778d1 --environment b46acc9a-5c76-4c7b-926e-12387a66fe2f --service 8aabd13f-b848-47ca-bd07-4588e7aaee3e
```

Não usar `--new`, não criar outro projeto e não enviar o ZIP como se fosse diretório de código.
Não aplicar configuração staged como substituto do upload: isso não inclui `deploy/server.py` na imagem.
Configurar o build por Dockerfile.railway nas configurações do serviço. A tentativa de usar railwayConfigFile recebeu aviso de depreciação da ferramenta; nenhum novo railway.json/railway.toml foi acrescentado. O .railwayignore exclui cópias legadas desses arquivos.
Antes de integração, verificar resposta HTTPS do /health, documentação protegida, rejeição sem token e respostas autenticadas reais. Reavaliar logs e réplicas, não apenas o rótulo SUCCESS.

## Escopo que permanece sem conclusão
Receita PED, Ventilação Mecânica, Soroterapia e Cardiologia no PA: identidade editável do plugin, código implantável e migração não confirmados. Não criados endpoints fictícios.
Mesclar e SitesGPTs: nenhum original editado. O arquivo MIGRATION_PLAN_NOT_APPLIED.json é apenas registro de preparo, não uma configuração já aplicada.
Não usar dados identificáveis de pacientes, não considerar o piloto aprovação de prescrição e não tornar regras/documentos médicos em API validada apenas por hospedá-los.

## Documentação técnica consultada
- https://docs.railway.com/cli/up
- https://docs.railway.com/cli/login
- https://docs.railway.com/deployments/healthchecks

Build Docker e publicação deste pacote não executados nesta sessão.

## Testes desta preparação
Base original: 12 testes aprovados. Pacote preparado: 41 testes aprovados (12 da base, 26 de segurança, 3 de consistência de versão). O teste antigo do healthcheck esperava 3.0.0; foi ajustado para usar a versão canônica do módulo, conferida também contra pyproject.toml. Nenhum teste clínico/posológico foi removido ou relaxado.
