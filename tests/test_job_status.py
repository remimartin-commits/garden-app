from __future__ import annotations
import unittest
from app.entities import Job, JobStatusDefinition

class TestJobStatusDefinition(unittest.TestCase):
    def test_create_job_status_definition(self):
        custom_status = JobStatusDefinition(name="Maintenance", description="Custom maintenance workflow")
        self.assertEqual(custom_status.name, "Maintenance")

    def test_assign_custom_status_to_job(self):
        custom_status = JobStatusDefinition(name="Maintenance", description="Custom maintenance workflow")
        job = Job(
            job_id=1,
            customer_id=1,
            property_id=1,
            description="Site visit",
            workflow_status=custom_status.name,
            system_status="scheduled",
        )
        self.assertEqual(job.workflow_status, "Maintenance")
        self.assertEqual(job.system_status, "scheduled")

if __name__ == '__main__':
    unittest.main()