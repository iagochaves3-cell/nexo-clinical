from __future__ import annotations
from typing import Any
from math import isfinite
from ..input_models import ECGInput

def assess_ecg_input(metadata: dict[str,Any]) -> dict[str,Any]:
    metadata = ECGInput.model_validate(metadata).model_dump(exclude_none=True)
    required=("format","lead_count","speed_mm_s","gain_mm_mv")
    missing=[k for k in required if metadata.get(k) in (None,"")]
    quality="insufficient" if missing else "assessable"
    warnings=[]
    if metadata.get("format") not in {"digital_signal","pdf_vector","image"}: warnings.append("Formato não reconhecido")
    if metadata.get("format")=="image": warnings.append("Fotografia é última opção; validar perspectiva, calibração e recorte")
    return {"quality":quality,"missing":missing,"warnings":warnings,
            "separation":["medidas determinísticas","interpretação algorítmica","decisão clínica final"]}

def qtc_bazett(qt_ms: float, rr_ms: float) -> float:
    _validate_intervals(qt_ms, rr_ms)
    return _finite_result(qt_ms/((rr_ms/1000)**0.5))

def qtc_fridericia(qt_ms: float, rr_ms: float) -> float:
    _validate_intervals(qt_ms, rr_ms)
    return _finite_result(qt_ms/((rr_ms/1000)**(1/3)))


def _validate_intervals(qt_ms: float, rr_ms: float) -> None:
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not isfinite(v) or v <= 0 for v in (qt_ms, rr_ms)):
        raise ValueError("QT e RR devem ser números positivos e finitos")


def _finite_result(value: float) -> float:
    if not isfinite(value):
        raise ValueError("Resultado não finito")
    return round(value, 1)
