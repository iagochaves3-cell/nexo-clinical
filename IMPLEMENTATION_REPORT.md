# Relatório de implementação — Nexo Clinical Knowledge Platform 3.0.0

## Estado

Implementação funcional e instalável criada para substituir o Nexo AI 2.x.

## Entregue

- Source Registry 1.0.0 incorporado ao pacote.
- Modelos Pydantic para fontes, recomendações, medicamentos, consultas e respostas.
- Knowledge Platform com validação obrigatória de proveniência.
- Clinical Rules Engine com falha segura.
- Núcleo determinístico de cálculos e unidades preservado da versão anterior.
- Roteamento para 14 domínios/especialistas.
- Safety Pipeline com detecção de ausência de peso, fonte, estabilidade não sustentada, baixa qualidade multimodal e identificadores pessoais.
- ECG: avaliação de entrada e QTc por Bazett/Fridericia.
- Laboratório: anion gap, sódio corrigido, osmolaridade estimada e fórmula de Winter.
- Imagem: gate de qualidade e preferência por DICOM.
- FastAPI, CLI, Dockerfile, prompts, documentação e evals.

## Validação local

- `python -m compileall`: aprovado.
- Testes automatizados: 11/11 aprovados.
- Evals locais: 3/3 aprovados.
- Wheel construído: `nexo_clinical_platform-3.0.0-py3-none-any.whl`.
- SHA-256: `5bd60baf9b2399294dd3ebaef32369837bde7fee3225e833808576b75dffa4fe`.

## Limites deliberados

O pacote não contém doses ou protocolos clínicos específicos preenchidos em massa. A ingestão desses dados deve ocorrer por domínio, com licença adequada, revisão humana dupla, versionamento, rastreabilidade e validação institucional. Os módulos multimodais entregues são infraestrutura e gates de qualidade, não modelos diagnósticos validados ou dispositivos médicos autorizados.

## Migração

1. Remover o pacote anterior `nexo-ai` do ambiente, se necessário.
2. Instalar o novo wheel.
3. Configurar `OPENAI_API_KEY` apenas no ambiente de execução.
4. Executar testes e `/health`.
5. Importar progressivamente recomendações e fármacos validados.
