from datetime import date
import pytest
from nexo_clinical.knowledge import KnowledgePlatform,KnowledgeError
from nexo_clinical.models import Recommendation

def test_recommendation_requires_registered_source():
    k=KnowledgePlatform(); item=Recommendation(recommendation_id="x",title="x",domain="emergency_adult",recommendation="x",source_ids=["MISSING"],version="1",effective_date=date.today(),last_reviewed=date.today())
    with pytest.raises(KnowledgeError): k.add_recommendation(item)
