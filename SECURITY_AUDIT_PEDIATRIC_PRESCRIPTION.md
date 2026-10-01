# Auditoria de Segurança: Geração de Prescrição Pediátrica

**Data**: 2026-10-01  
**Versão do código**: 8ea90462d252d178bac839209e8627151e644cce  
**Severidade Global**: 🔴 **CRÍTICA** — Descumprimento de contrato de governança + desvios de validação  

---

## Resumo Executivo

A função `generate_pediatric_prescription()` em `pediatric_pharmacotherapy.py` **infringe 11 dos 12 requisitos não-negociáveis** da governança configurada em `pediatric-pharmacotherapy-governance.yaml`:

1. ✅ Retorna `requires_human_review=True` (correto)
2. ✅ Retorna `clinical_validated=False` (correto)
3. ✅ Retorna `prescribing_authorization=False` (correto)
4. ❌ **Inventa ondansetrona 0,8 mg/mL** quando apresentação real é 8 mg/mL (Brasil, verificado 2026-08-24)
5. ❌ **Ignora contraindicações** (sem peso por idade, alergias, comorbidades, função renal)
6. ❌ **Substring matching negativo quebra** ("sem otite" → otite, "sem faringite" → faringite)
7. ❌ **Sem validação de idade estruturada** (aceita string arbitrária)
8. ❌ **Datas impossíveis aceitas** (2026-02-30, 1800-01-01)
9. ❌ **Texto livre não sanitizado** (quebras de linha injetadas)
10. ❌ **Peso extremo sem limite pediátrico** (90 kg aceito, recém-nascido <0.5 kg não validado)
11. ❌ **Fallback genérico sem indicação** (diagnóstico desconhecido = medicamentos genéricos)
12. ❌ **Sem rastreamento de apresentação** (hardcoded, sem vinculação a governança)

---

## 1. CONCENTRAÇÃO CRÍTICA DE ONDANSETRONA

### Dados de Fato

**`presentations_brazil_v61.json` (verificado 2026-08-24)**:
```json
{
  "presentation_id": "ondansetron-enavo-drops-8mg-ml-5ml-br",
  "strength": { "value": 8, "unit": "mg/mL" },
  "dosage_form": "solução oral em gotas",
  "drops_per_mL": 20,
  "active_mg_per_drop": 0.4
}
```

**`pediatric_pharmacotherapy.py` (linhas 74-78)**:
```python
ml_ondansetrona = min(weight * 0.1875, 5.0)
"2. ONDANSETRONA 0,8 MG/ML SOLUÇÃO ORAL ---\nDar {ml_ondansetrona:.1f} mL..."
```

### Problema

- **Apresentação real**: 8 mg/mL
- **Código usa**: 0,8 mg/mL (10× menor)
- **Cálculo esperado**: dose 0,1–0,15 mg/kg ÷ 8 mg/mL = 0,0125–0,01875 mL/kg
- **Código calcula**: weight × 0,1875 mL (presume 0,8 mg/mL)
- **Resultado**: **Prescreve ~3 mL de 8 mg/mL quando deveria prescrever ~0,3 mL**
- **Impacto clínico**: Overdose **10×** de ondansetrona

### Classificação

- **Severidade**: 🔴 **CRÍTICA** (alto risco de toxicidade)
- **Violação de governança** (linha 17): "Never invent dose, presentation, concentration"
- **Teste que falha**: `test_generate_prescription_gastro_path()` linha 33 valida "ONDANSETRONA 0,8 MG/ML" em string, não valida dose ml

---

## 2. SUBSTRING MATCHING NEGATIVO

### Problema

**Linhas 47, 73, 101**: Usa `"x" in normalized` sem limite de palavra

```python
normalized = diagnosis.casefold()  # "sem faringite viral" → "sem faringite viral"
if any(x in normalized for x in ("faringite", "garganta", "resfriado", "ivas")):
    # Ativa bloco de faringite
```

### Cenários de Falha

| Entrada | Esperado | Atual | Resultado |
|---------|----------|-------|-----------|
| "Sem faringite" | Fallback genérico | Trata como faringite | ❌ Prescreve dipirona |
| "Sem otite" | Fallback genérico | Trata como otite | ❌ Prescreve amoxicilina |
| "Faringoamigdalite" | Trata como faringite | Trata como faringite | ✅ OK |
| "Asfixia" | Fallback genérico | Trata como IVAS | ❌ Prescreve ibuprofeno |
| "Laringe-garganta" | Fallback genérico | Trata como garganta | ❌ Prescreve dipirona |

### Classificação

- **Severidade**: 🟠 **ALTA** (prescrição incorreta por diagnóstico)
- **Violação de governança** (linha 39): "diagnosis_relation_is_explicit" – não é explícita com substring
- **Teste que falha**: Nenhum teste cobre negativas ou compostas

---

## 3. ONDANSETRONA 0,8 MG/ML NÃO EXISTE NO BRASIL

### Verificação de Apresentações Registradas

**`presentations_brazil_v61.json` contém**:
- ✅ Ondansetrona 8 mg/mL (marca Enavo, gotas)
- ✅ Cetirizina 1 mg/mL

**`presentations_brazil_v61.json` NÃO contém**:
- ❌ Ondansetrona 0,8 mg/mL
- ❌ Dipirona 500 mg/mL (gotas) — apenas referência em código
- ❌ Ibuprofeno 100 mg/mL (gotas) — apenas referência em código
- ❌ Amoxicilina 250 mg/5 mL — apenas referência em código

### Impacto

- Código **prescreve concentrações não verificadas**
- Violação de governança (linha 42): "brazilian_presentation_verified"
- **Sem integração com registry** → risco de prescrever "ilegalmente"

---

## 4. VALIDAÇÃO DE IDADE INEXISTENTE

### Entrada Aceita

```python
class PediatricPrescriptionInput(StrictInput):
    age: str = Field(min_length=1, max_length=120)  # Qualquer string
```

### Exemplos de Falha

| Entrada | Esperado | Atual | Validado? |
|---------|----------|-------|-----------|
| `"2 anos"` | Interpretável | Não faz parse | ❌ String literal |
| `"2y"` | Interpretável | Não faz parse | ❌ String literal |
| `"24 meses"` | Interpretável | Não faz parse | ❌ String literal |
| `"abc"` | Rejeitar | Aceita | ❌ FALHA |
| `"-5 anos"` | Rejeitar | Aceita | ❌ FALHA |
| `"500 anos"` | Rejeitar | Aceita | ❌ FALHA |
| `""` (vazio) | Rejeitar | Rejeita (min_length=1) | ✅ OK |

### Problema no Cálculo

- **Peso** validado: `Field(gt=0, le=90)` (0 < x ≤ 90 kg)
- **Idade** validado: `Field(min_length=1, max_length=120)` (qualquer string)
- **Fórmulas de dose** usam **apenas peso**, nunca idade
- **Resultado**: Prescrições identicamente erradas para recém-nascido e criança de 12 anos com mesmo peso

### Classificação

- **Severidade**: 🟠 **ALTA** (dose inadequada por idade não considerada)
- **Violação de governança** (linha 40): "patient_population_matches" requer validação de idade

---

## 5. DATAS IMPOSSÍVEIS ACEITAS

### Validação de Data

```python
def _fmt_date(value: str | None) -> str:
    return value.strip() if value and value.strip() else date.today().strftime("%d/%m/%Y")
```

### Exemplos de Falha

| Entrada | Validação | Aceita? |
|---------|-----------|---------|
| `"2026-02-30"` | Sem parse de data | ✅ Aceita |
| `"1800-01-01"` | Sem parse de data | ✅ Aceita |
| `"3000-12-31"` | Sem parse de data | ✅ Aceita |
| `"abc/def/ghi"` | Sem parse de data | ✅ Aceita |
| `None` | Substitui por hoje | ✅ OK |

### Classificação

- **Severidade**: 🟡 **MÉDIA** (afeta auditoria, não dose)
- **Violação de governança** (linha 54–58): "Reverse-check the rounded practical amount" requer data válida para auditoria

---

## 6. PESO EXTREMO SEM LIMITE PEDIÁTRICO

### Validação Atual

```python
class PediatricPrescriptionInput(StrictInput):
    weight_kg: float = Field(gt=0, le=90)  # 0 < x ≤ 90
```

### Problema

- **Limite superior**: 90 kg (adolescente grande, aceitável)
- **Limite inferior**: > 0 (inclui 0,0001 kg = 0,1 g)
- **Recém-nascidos**: 2,5–4,0 kg ✅
- **Prematuros**: 0,5–2,5 kg ❌ (rejeita 0,5–1,5 kg)

### Fórmulas de Dose vs. Peso

```python
gotas_dipirona = min(round(weight * 0.6), 40)   # Sem limite mínimo
gotas_ibuprofeno = min(round(weight * 1.5), 40)  # Sem limite mínimo
ml_ondansetrona = min(weight * 0.1875, 5.0)      # Sem limite mínimo
ml_amox = min(weight * 0.33, 10.0)               # Sem limite mínimo
```

### Cenários de Falha

| Peso | Esperado | Cálculo | Resultado |
|------|----------|---------|-----------|
| 0,5 kg (prematuro) | Rejeitar | Não permite | ✅ Rejeita entrada |
| 1,5 kg (prematuro) | Rejeitar | Não permite | ✅ Rejeita entrada |
| 2,5 kg (recém-nascido) | Calcular dose mínima | 1,5 gotas dipirona | ❌ Sem limite mínimo |
| 0,1 kg (erro) | Rejeitar | Aceita | ❌ FALHA |
| 150 kg (erro) | Rejeitar | Rejeita (le=90) | ✅ OK |

### Classificação

- **Severidade**: 🟠 **ALTA** (prematuros/recém-nascidos mal suportados)
- **Violação de governança** (linha 40): "patient_population_matches" deve incluir todas as idades pediátricas

---

## 7. INJEÇÃO DE QUEBRAS DE LINHA

### Campos Não Sanitizados

```python
diagnosis = (diagnosis or "").strip()  # Strip remove espaços, não \n
age = (age or "").strip()               # Strip remove espaços, não \n
visit = _fmt_date(visit_date)            # Sem sanitização
```

### Vetor de Ataque

```python
generate_pediatric_prescription(
    diagnosis="Faringite\n\n=== SEÇÃO INJETADA ===",
    weight_kg=10,
    age="2 anos\nMODIFIED_CLAIM",
    visit_date="28/09/2026\nATAQUE"
)
```

### Saída Corrompida

```
DIAGNÓSTICO
FARINGITE

=== SEÇÃO INJETADA ===
PESO
10 kg
IDADE
2 anos
MODIFIED_CLAIM
...
```

### Classificação

- **Severidade**: 🟠 **ALTA** (execução de comando potencial, manipulação de auditoria)
- **Violação de governança** (linha 62): "triple_audit" requer integridade textual

---

## 8. CONTRAINDICAÇÕES AUSENTES

### Campos Não Considerados

| Campo | Esperado | Atual | Risco |
|-------|----------|-------|-------|
| Alergias | Rejeitar se alérgico | Ignora | Anafilaxia |
| Comorbidades | Terapia ajustada | Ignora | Insuficiência hepática/renal |
| Medicamentos em uso | Interações | Ignora | Evento adverso |
| Função renal | Ajustar dose | Ignora | Acúmulo tóxico |
| Função hepática | Ajustar dose | Ignora | Toxicidade hepática |
| Gravidez (mãe) | N/A | N/A | N/A (pediátrico) |
| Amamentação | Transferência de droga | Ignora | Intoxicação do bebê |

### Governança Exigida

```yaml
allowed_resolution_states:
  REQUIRES_CRITICAL_INPUT: "DADO CLÍNICO OBRIGATÓRIO AUSENTE: {field}"
```

### Classificação

- **Severidade**: 🔴 **CRÍTICA** (impossível validar segurança clínica)
- **Violação de governança** (múltiplas linhas): "Never invent", "Off-label", "Evidence-limited specialist practice"

---

## 9. FALLBACK GENÉRICO SEM INDICAÇÃO

### Diagnóstico Desconhecido

```python
else:
    # Fallback: qualquer diagnóstico não reconhecido
    uso_oral.extend([...])  # Dipirona + Ibuprofeno genéricos
```

### Exemplos de Falha

| Diagnóstico | Esperado | Atual | Resultado |
|------------|----------|-------|-----------|
| "Intoxicação por paracetamol" | Rejeitar | Prescreve ibuprofeno | ❌ FATAL |
| "Hipoglicemia" | Prescrever glicose | Prescreve dipirona | ❌ INADEQUADO |
| "Choque séptico" | Chamar pediatra | Prescreve ibuprofeno | ❌ INADEQUADO |
| "Convulsão" | Chamar pediatra | Prescreve dipirona | ❌ INADEQUADO |
| "Esôfago de Barrett" | Dieta/endoscopia | Prescreve ibuprofeno | ❌ CONTRAINDIC. |

### Classificação

- **Severidade**: 🔴 **CRÍTICA** (prescrição without clinical basis)
- **Violação de governança** (linha 39): "default: deny" — fallback deveria rejeitar

---

## 10. TESTES INCOMPLETOS

### Cobertura Atual de `test_pediatric_pharmacotherapy.py`

```python
# Linhas 21–48: Testes de caso feliz (3 caminhos + fallback)
def test_generate_prescription_faringitis_path(): ✅ Caminh
o 1
def test_generate_prescription_gastro_path(): ✅ Caminho 2 (FALHA)
def test_generate_prescription_bacterial_path(): ✅ Caminho 3
def test_generate_prescription_generic_fallback(): ✅ Fallback

# Linhas 51–57: Testes de validação (apenas requeridos, não limites)
def test_generate_prescription_validates_required_fields(): ✅ Campos vazios
```

### Cobertura Ausente (Crítica)

- ❌ Substring matching negativo: `"Sem faringite"`, `"Sem otite"`
- ❌ Dose computada vs. apresentação registrada
- ❌ Idade impossível: `"abc"`, `"-5"`, `"500 anos"`
- ❌ Data impossível: `"2026-02-30"`, `"1800-01-01"`
- ❌ Peso extremo: `0,0001 kg`, `150 kg`
- ❌ Injeção de quebra de linha: `"Faringite\n\nINJETADO"`
- ❌ Ondansetrona: verificação de dose vs. 8 mg/mL real

### Falha em Teste Existente

**Linha 33**: `assert "ONDANSETRONA 0,8 MG/ML SOLUÇÃO ORAL" in text`
- Testa **string literal** em output, não testa dose
- **Deveria falhar** quando corrigido para 8 mg/mL

---

## 11. SEM INTEGRAÇÃO COM REGISTRY

### Governança Exigida

```yaml
selector_policy:
  selectable_only_when:
    - diagnosis_relation_is_explicit
    - patient_population_matches
    - complete_operational_regimen
    - brazilian_presentation_verified  ← NÃO VERIFICADO
    - regimen_level_source_present
    - triple_audit_passed
```

### Verificação Atual

```python
# Sem integração com SourceRegistry
# Sem integração com presentations_brazil_v61.json
# Sem integração com pediatric-pharmacotherapy-governance.yaml
# Sem ligação com triple_audit (structural, pharmaceutical, clinical)
```

### Classificação

- **Severidade**: 🟠 **ALTA** (quebra de cadeia de custódia)
- **Violação de governança** (linha 42): "brazilian_presentation_verified"

---

## 12. FALTA DE RASTREAMENTO DE VERSÃO

### Versão de Governança

```yaml
configuration:
  id: pediatric-pharmacotherapy-governance
  version: 61.0-diagnosis-linked-complete-regimens
  effective_date: 2026-08-24
```

### Código Não Registra

```python
# Sem __version__ ou metadata
# Sem referência a "pediatric-pharmacotherapy-governance:61.0"
# Sem timestamp de efetividade (2026-08-24)
```

### Classificação

- **Severidade**: 🟡 **MÉDIA** (afeta auditoria)

---

## Tabela de Severidade Resumida

| # | Problema | Severidade | Impacto | Teste Falha? |
|---|----------|-----------|--------|-------------|
| 1 | Ondansetrona 0,8 vs. 8 mg/mL | 🔴 CRÍTICA | Overdose 10× | Sim |
| 2 | Substring matching negativo | 🟠 ALTA | Prescrição errada | Não coberto |
| 3 | Apresentação desverificada | 🟠 ALTA | Fora de governança | Não coberto |
| 4 | Validação de idade ausente | 🟠 ALTA | Dose inadequada | Não coberto |
| 5 | Data impossível aceita | 🟡 MÉDIA | Auditoria falha | Não coberto |
| 6 | Peso extremo sem limite | 🟠 ALTA | Prematuro rejeitado | Não coberto |
| 7 | Injeção de quebra de linha | 🟠 ALTA | Auditoria corrompida | Não coberto |
| 8 | Sem contraindicações | 🔴 CRÍTICA | Evento adverso | Não testado |
| 9 | Fallback genérico | 🔴 CRÍTICA | Prescrição insegura | Teste falha parcial |
| 10 | Testes incompletos | 🔴 CRÍTICA | Não detecta erros | N/A |
| 11 | Sem integração registry | 🟠 ALTA | Fora de governança | Não coberto |
| 12 | Sem rastreamento versão | 🟡 MÉDIA | Auditoria falha | Não coberto |

---

## Recomendações Imediatas

### 🔴 BLOQUEADOR: Não publicar em produção sem correções críticas

1. **Corrigir concentração ondansetrona** (crítico):
   - Mudar `0,8 mg/mL` para `8 mg/mL`
   - Recalcular fórmula: `ml = weight_kg * 0.1 / 8` (para dose 0,1 mg/kg)
   - Teste: `assert "ONDANSETRONA 8 MG/ML" in text`
   - Teste: `assert "Dar 0.1 mL" in text` (para 1 kg)

2. **Implementar validação de idade estruturada** (crítico):
   - Aceitar `AgeInput` com tipo (`years`, `months`, `days`)
   - Convertir para meses ou dias para cálculo
   - Rejeitar idade < 0 ou > 18 anos
   - Usar em fórmulas de dose

3. **Implementar parser de data seguro** (crítico):
   - Validar formato `%d/%m/%Y` ou ISO 8601
   - Rejeitar data > hoje
   - Rejeitar data < 1970

4. **Implementar substring matching seguro** (crítico):
   - Usar regex com word boundaries: `r"\b(faringite|garganta|resfriado|ivas)\b"`
   - Rejeitar diagnósticos que começam com "sem ", "negativo", "ausência"
   - Teste explícito para negativas

5. **Integrar com registry** (crítico):
   - Validar cada medicamento contra `presentations_brazil_v61.json`
   - Desconhecer apresentação → `ResolutionState.REQUIRES_CRITICAL_INPUT`
   - Documentar cada medicamento com `source_ids`

### 🟠 ALTA PRIORIDADE: Corrigir antes de qualquer deployment

6. **Adicionar sanitização de entrada** (alta):
   - Rejeitar `\n`, `\r`, `\t` em `diagnosis`, `age`
   - Rejeitar caracteres não-ASCII em `visit_date`

7. **Expandir cobertura de testes** (alta):
   - Negativos para substring matching
   - Bordas de peso: 0,5 kg, 2,5 kg, 90 kg, 90,1 kg
   - Bordas de idade: 0 anos, 18 anos, 19 anos
   - Data impossível
   - Injeção

8. **Documentar governança ativa** (alta):
   - Adicionar `__version__ = "3.1.0.pediatric"` com referência a governance:61.0
   - Adicionar comentário com linha da governança para cada validação

### 🟡 MÉDIA PRIORIDADE: Próxima sprint

9. Rejeitar diagnóstico desconhecido com mensagem clara
10. Adicionar suporte a contraindicações (alergias mínimas)
11. Adicionar logging de auditoria com rastreamento de versão

---

## Conclusão

A função `generate_pediatric_prescription()` **viola a governança de segurança crítica** configurada no repositório. Publicar em produção **expõe risco clínico crítico** (overdose de ondansetrona, fallback genérico para intoxicação, rejeição de prematuros).

**Recomendação final**: Bloquear qualquer deployment até que todas as 5 vulnerabilidades críticas (1, 2, 4, 8, 9) sejam corrigidas e testadas.
