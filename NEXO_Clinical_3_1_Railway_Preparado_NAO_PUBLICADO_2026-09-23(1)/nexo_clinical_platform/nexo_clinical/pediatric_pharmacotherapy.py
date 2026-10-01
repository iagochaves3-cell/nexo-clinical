from dataclasses import dataclass
from datetime import date
from enum import StrEnum
import math
from typing import Iterable
class ResolutionState(StrEnum):
 READY="READY"; CONTRAINDICATED_AGE="CONTRAINDICATED_AGE"; CONTRAINDICATED_WEIGHT="CONTRAINDICATED_WEIGHT"; CONTRAINDICATED_CLINICAL="CONTRAINDICATED_CLINICAL"; NOT_INDICATED_FOR_DIAGNOSIS="NOT_INDICATED_FOR_DIAGNOSIS"; SPECIALIST_ONLY="SPECIALIST_ONLY"; REQUIRES_CRITICAL_INPUT="REQUIRES_CRITICAL_INPUT"; REGULATORY_SUSPENDED="REGULATORY_SUSPENDED"
@dataclass(frozen=True)
class RegimenEligibility:
 regimen_id:str; medication_id:str; diagnosis_ids:tuple[str,...]; role:str; clinical_target:str; source_ids:tuple[str,...]; presentation_verified_brazil:bool; completeness_status:str; triple_audit_status:str; calculation_component:str; active:bool=True
 def executable(self): return bool(self.active and self.source_ids and self.presentation_verified_brazil and self.completeness_status=="COMPLETE" and self.triple_audit_status=="PASSED" and self.calculation_component.strip())
def diagnosis_linked_candidates(regimens:Iterable[RegimenEligibility],diagnosis_id:str,role:str|None=None): return [r for r in regimens if r.active and diagnosis_id in r.diagnosis_ids and (role is None or r.role==role) and r.executable()]
def diagnosis_linked_adjuncts(regimens:Iterable[RegimenEligibility],diagnosis_id:str): return diagnosis_linked_candidates(regimens,diagnosis_id,"adjunct")


def _lines(items:list[str])->str: return "\n".join(items)


def _validate_weight(weight_kg:float)->float:
 if not math.isfinite(weight_kg) or weight_kg<=0: raise ValueError("weight_kg deve ser positivo e finito.")
 return weight_kg


def _fmt_date(value:str|None)->str: return value.strip() if value and value.strip() else date.today().strftime("%d/%m/%Y")


def generate_pediatric_prescription(diagnosis:str, weight_kg:float, age:str, visit_date:str|None=None)->str:
 diagnosis=(diagnosis or "").strip()
 age=(age or "").strip()
 if not diagnosis: raise ValueError("diagnosis é obrigatório.")
 if not age: raise ValueError("age é obrigatório.")
 weight=_validate_weight(weight_kg)
 normalized=diagnosis.casefold()
 visit=_fmt_date(visit_date)

 gotas_dipirona=min(round(weight*0.6),40)
 gotas_ibuprofeno=min(round(weight*1.5),40)
 uso_oral:list[str]=[]
 uso_nasal:list[str]=[]
 uso_inalatorio:list[str]=[]
 recomendacoes:list[str]=[]
 orientacoes:list[str]=[]
 evolucao:list[str]=[]
 sinais_alarme:list[str]=[]
 retorno="Retorno em caso de surgimento de qualquer sinal de alarme ou piora do estado geral da criança."

 if any(x in normalized for x in ("faringite","garganta","resfriado","ivas")):
  uso_oral.extend([
   f"1. DIPIRONA SÓDICA 500 MG/ML GOTAS ---\nDar {gotas_dipirona} gotas por via oral a cada 6 horas se houver febre (temperatura axilar a partir de 37,5°C) ou dor.",
   f"2. IBUPROFENO 100 MG/ML GOTAS ---\nDar {gotas_ibuprofeno} gotas por via oral a cada 8 horas durante 3 dias para o desconforto e inflamação da garganta.",
  ])
  uso_nasal.append("1. SORO FISIOLÓGICO 0,9% ---\nRealizar lavagem com 5 mL em cada narina com seringa a cada 3 a 4 horas para fluidificar as secreções e desobstruir as vias aéreas.")
  recomendacoes=[
   "- Oferecer líquidos frescos ou em temperatura ambiente com alta frequência ao longo do dia.",
   "- Priorizar alimentos macios, pastosos e não ácidos (sopas mornas, purês, frutas amassadas).",
   "- Manter repouso relativo da criança em ambiente ventilado e arejado.",
   "- Evitar exposição à fumaça, poeira e odores irritantes fortes.",
  ]
  orientacoes=[
   "- Nunca utilize remédios descongestionantes nasais de adulto ou sprays vasoconstritores.",
   "- Não administrar anti-inflamatórios em jejum ou se a criança apresentar vômitos constantes.",
  ]
  evolucao=[
   "- A dor na garganta e a recusa para engolir costumam melhorar progressivamente em até 72 horas.",
   "- A febre costuma ceder em até 3 dias conforme o controle dos sintomas.",
  ]
  sinais_alarme=[
   "- Dificuldade importante para engolir a própria saliva (criança babando excessivamente).",
   "- Respiração rápida, ofegante ou com afundamento das costelas ao respirar.",
   "- Prostração profunda, fraqueza excessiva ou sonolência exagerada com dificuldade para despertar.",
   "- Febre persistente por mais de 72 horas ou que não responde aos antitérmicos.",
  ]
 elif any(x in normalized for x in ("gastro","diarreia","vomito","vômito")):
  ml_ondansetrona=min(weight*0.1875,5.0)
  gotas_dip=min(round(weight*0.5),35)
  uso_oral.extend([
   "1. SAIS DE REIDRATAÇÃO ORAL (SACHÊ) ---\nDiluir 1 sachê em 1 litro de água filtrada e oferecer em pequenos goles ou colheradas após cada evacuação líquida ou episódio de vômito por 5 dias.",
   f"2. ONDANSETRONA 0,8 MG/ML SOLUÇÃO ORAL ---\nDar {ml_ondansetrona:.1f} mL por via oral a cada 8 horas apenas se a criança apresentar vômitos ou ânsias frequentes.",
   f"3. DIPIRONA SÓDICA 500 MG/ML GOTAS ---\nDar {gotas_dip} gotas por via oral a cada 6 horas se dor de barriga ou febre (temperatura axilar a partir de 37,5°C).",
  ])
  recomendacoes=[
   "- Hidratação rigorosa: água, soro caseiro/oral e água de coco oferecidos de forma fracionada (de colher em colher).",
   "- Alimentação leve sem forçar grandes volumes (arroz, batata, cenoura, maçã raspada, banana-maçã).",
   "- Higienizar as mãos com água e sabão com frequência, especialmente antes das refeições e após cada troca de fralda.",
   "- Suspender temporariamente alimentos muito doces, frituras e leite com teor elevado de gordura.",
  ]
  orientacoes=[
   "- Nunca utilize medicamentos para travar o intestino (como loperamida).",
   "- Evite anti-inflamatórios (como ibuprofeno ou cetoprofeno) em episódios de desidratação ou vômitos recorrentes.",
  ]
  evolucao=[
   "- Os episódios de vômito tendem a reduzir consideravelmente nas primeiras 24 a 48 horas.",
   "- A diarreia pode durar de 5 a 7 dias, tornando-se progressivamente mais pastosa.",
  ]
  sinais_alarme=[
   "- Ausência de urina por mais de 6 horas ou fraldas secas por longo período.",
   "- Olhos fundos, boca seca, lábios rachados ou choro sem lágrimas (sinais de desidratação).",
   "- Vômitos intensos e incoercíveis que impedem a criança de beber até mesmo pequenos goles de água.",
   "- Presença de sangue nas fezes ou dor abdominal contínua e insuportável.",
  ]
 elif any(x in normalized for x in ("otite","amigdalite","sinusite")):
  ml_amox=min(weight*0.33,10.0)
  uso_oral.extend([
   f"1. AMOXICILINA 250 MG/5 ML SUSPENSÃO ORAL ---\nDar {ml_amox:.1f} mL por via oral a cada 8 horas durante 10 dias rigorosamente nos horários certos.",
   f"2. DIPIRONA SÓDICA 500 MG/ML GOTAS ---\nDar {gotas_dipirona} gotas por via oral a cada 6 horas em caso de dor ou febre (temperatura axilar a partir de 37,5°C).",
   f"3. IBUPROFENO 100 MG/ML GOTAS ---\nDar {gotas_ibuprofeno} gotas por via oral a cada 8 horas durante 3 dias para alívio da dor intensa e inflamação.",
  ])
  if "sinusite" in normalized or "otite" in normalized:
   uso_nasal.append("1. SORO FISIOLÓGICO 0,9% ---\nRealizar lavagem nasal com seringa aplicando 5 a 10 mL em cada narina a cada 3 horas para drenagem de secreções.")
  recomendacoes=[
   "- Oferecer alimentação pastosa e líquidos em temperatura morna ou fria.",
   "- Não molhar o ouvido afetado durante o banho enquanto houver tratamento (caso de otite).",
   "- Repouso domiciliar adequado para recuperação da imunidade.",
  ]
  orientacoes=[
   "- Cumprir os 10 dias completos do antibiótico sem interrupções mesmo após a melhora evidente dos sintomas.",
   "- Não pingar remédios ou soluções caseiras dentro do ouvido sem orientação médica.",
  ]
  evolucao=[
   "- Redução expressiva da dor e da febre em 48 a 72 horas após o início do antibiótico.",
   "- Normalização do apetite e da disposição geral conforme a recuperação.",
  ]
  sinais_alarme=[
   "- Inchaço, vermelhidão ou dor atrás da orelha.",
   "- Febre alta persistente mesmo após 48 horas de antibiótico contínuo.",
   "- Dificuldade respiratória, sonolência excessiva ou rigidez no pescoço.",
  ]
 else:
  uso_oral.extend([
   f"1. DIPIRONA SÓDICA 500 MG/ML GOTAS ---\nDar {gotas_dipirona} gotas por via oral a cada 6 horas se houver febre (temperatura axilar a partir de 37,5°C) ou dor.",
   f"2. IBUPROFENO 100 MG/ML GOTAS ---\nDar {gotas_ibuprofeno} gotas por via oral a cada 8 horas se houver dor ou inflamação durante 3 dias.",
  ])
  recomendacoes=[
   "- Manter a criança muito bem hidratada com água, sucos naturais e caldos leves.",
   "- Repouso domiciliar adequado em ambiente tranquilo e arejado.",
  ]
  orientacoes=[
   "- Respeitar rigorosamente o intervalo mínimo entre os medicamentos.",
   "- Não fornecer remédios sem recomendação médica prévia.",
  ]
  evolucao=["- Melhora gradual dos sintomas nas próximas 48 a 72 horas com os cuidados domiciliares."]
  sinais_alarme=[
   "- Respiração rápida ou cansaço para respirar.",
   "- Prostração intensa, vômitos contínuos ou febre que não cede após 72 horas.",
  ]

 output=[f"DIAGNÓSTICO\n{diagnosis.upper()}",f"PESO\n{weight:g} kg",f"IDADE\n{age}",f"DATA\n{visit}"]
 if uso_oral: output.append("USO ORAL\n\n"+_lines(uso_oral))
 if uso_nasal: output.append("USO NASAL\n\n"+_lines(uso_nasal))
 if uso_inalatorio: output.append("USO INALATÓRIO\n\n"+_lines(uso_inalatorio))
 output.extend([
  "RECOMENDAÇÕES\n"+_lines(recomendacoes),
  "ORIENTAÇÕES GERAIS\n"+_lines(orientacoes),
  "EVOLUÇÃO CLÍNICA ESPERADA\n"+_lines(evolucao),
  "SINAIS DE ALARME\n"+_lines(sinais_alarme),
  "RETORNO/REAVALIAÇÃO\n"+retorno,
 ])
 return "\n\n".join(output)
