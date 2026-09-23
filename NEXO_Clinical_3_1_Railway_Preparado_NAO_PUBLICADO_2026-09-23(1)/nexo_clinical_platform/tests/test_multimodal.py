from nexo_clinical.multimodal.ecg import qtc_bazett,assess_ecg_input
from nexo_clinical.multimodal.laboratory import anion_gap,winter_expected_pco2
from nexo_clinical.multimodal.imaging import assess_image_input

def test_qtc(): assert qtc_bazett(400,1000)==400.0
def test_ecg_quality(): assert assess_ecg_input({"format":"image"})["quality"]=="insufficient"
def test_lab(): assert anion_gap(140,104,24)==12.0; assert winter_expected_pco2(12)["expected"]==26.0
def test_image(): assert assess_image_input({"format":"dicom"})["human_review_required"] is True
