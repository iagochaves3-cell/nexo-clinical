from __future__ import annotations
from typing import Any

def assess_image_input(metadata:dict[str,Any])->dict[str,Any]:
    fmt=metadata.get("format")
    warnings=[]
    if fmt=="dicom":
        required=("modality","study_uid","series_uid")
    else:
        required=("modality","body_region","view")
        warnings.append("Preferir DICOM/DICOMweb para preservar metadados, escala e orientação")
    missing=[k for k in required if not metadata.get(k)]
    return {"quality":"insufficient" if missing else "assessable","missing":missing,"warnings":warnings,
            "human_review_required":True}
