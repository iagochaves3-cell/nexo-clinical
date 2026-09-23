from __future__ import annotations
from typing import Any

def assess_ecg_input(metadata: dict[str,Any]) -> dict[str,Any]:
    required=("format","lead_count","speed_mm_s","gain_mm_mv")
    missing=[k for k in required if metadata.get(k) in (None,"")]
    quality="insufficient" if missing else "assessable"
    warnings=[]
    if metadata.get("format") not in {"digital_signal","pdf_vector","image"}: warnings.append("Formato não reconhecido")
    if metadata.get("format")=="image": warnings.append("Fotografia é última opção; validar perspectiva, calibração e recorte")
    return {"quality":quality,"missing":missing,"warnings":warnings,
            "separation":["medidas determinísticas","interpretação algorítmica","decisão clínica final"]}

def qtc_bazett(qt_ms: float, rr_ms: float) -> float:
    if qt_ms<=0 or rr_ms<=0: raise ValueError("QT e RR devem ser positivos")
    return round(qt_ms/((rr_ms/1000)**0.5),1)

def qtc_fridericia(qt_ms: float, rr_ms: float) -> float:
    if qt_ms<=0 or rr_ms<=0: raise ValueError("QT e RR devem ser positivos")
    return round(qt_ms/((rr_ms/1000)**(1/3)),1)
