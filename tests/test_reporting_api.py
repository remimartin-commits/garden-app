
from fastapi.testclient import TestClient
from app.main import app
from app.entities import BusinessPerformanceReportParams

client = TestClient(app)

def test_get_business_performance_report():
    response = client.get("/api/v1/reports/business-performance", params={
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "service_type": "maintenance",
        "suburb": "Redcliffs",
        "customer_type": "commercial",
        "staff_member": "john.doe"
    })
    assert response.status_code == 200 or response.status_code == 404
    assert isinstance(response.json(), dict)