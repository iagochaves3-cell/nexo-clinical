from __future__ import annotations
SPECIALISTS={
 "emergency_adult":"Emergência adulta", "emergency_pediatrics":"Emergência pediátrica",
 "critical_care":"Terapia intensiva", "pharmacology":"Farmacologia clínica",
 "toxicology":"Toxicologia", "infectious_diseases":"Infectologia e antimicrobianos",
 "cardiology_ecg":"Cardiologia e ECG", "neurology":"Neurologia", "trauma":"Trauma",
 "laboratory":"Laboratório e gasometria", "radiology":"Imagem médica",
 "documentation":"Documentação clínica", "evidence":"Síntese de evidências", "safety":"Revisão de segurança"
}
KEYWORDS={
 "emergency_pediatrics":("criança","pediatr","lactente","recém-nasc"),
 "cardiology_ecg":("ecg","eletrocard","arritmia","qt","st "),
 "laboratory":("gasometr","sódio","potássio","lactato","hemograma","creatinina"),
 "radiology":("radiografia","tomografia","ultrassom","dicom","imagem"),
 "pharmacology":("dose","diluição","ampola","infusão","ml/h","medicamento"),
 "infectious_diseases":("antibiótico","sepse","infecção","antimicrob"),
 "toxicology":("intox","antídoto","overdose","envenen"),
 "neurology":("convuls","avc","cefaleia","neurol"),
 "trauma":("trauma","tce","fratura","atls")
}
def route_specialists(text:str, domain_hint:str|None=None)->list[str]:
    low=text.casefold(); out=[]
    if domain_hint in SPECIALISTS: out.append(domain_hint)
    for k,words in KEYWORDS.items():
        if any(w in low for w in words) and k not in out: out.append(k)
    if not out: out.append("emergency_adult")
    for required in ("evidence","safety"):
        if required not in out: out.append(required)
    return out
