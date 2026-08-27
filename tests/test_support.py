"""Shared database fixture for the assessment screen integration tests."""

import unittest

from app import app, get_db_connection


class AssessmentTestCase(unittest.TestCase):
    """Give each test an isolated database and Flask test client."""

    def setUp(self):
        self.conn = get_db_connection()
        self.conn.execute("DELETE FROM assessments")
        self.conn.execute("DELETE FROM facilities")
        self.conn.commit()
        self.client = app.test_client()

    def tearDown(self):
        self.conn.execute("DELETE FROM assessments")
        self.conn.execute("DELETE FROM facilities")
        self.conn.commit()
        self.conn.close()

    def insert_assessment(
        self,
        assessment_name: str = "Sunrise Learning Center - Annual 2026 test",
        assessment_date: str = "2026-07-17",
        visit_date: str = "2026-07-14",
    ) -> int:
        """Insert the facility and assessment shape used by most tests."""
        facility_id = self.conn.execute(
            """
            INSERT INTO facilities (
                identifier, name, license_number, physical_address,
                city_state_postal_code, type, provider_name, provider_id,
                region, program_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "FAC-008742", assessment_name, "LIC-CC-21884",
                "1250 Cedar Avenue", "Olympia, WA 98501", "Mixed Age Center",
                "Sunrise Learning LLC", "PRV-004198",
                "Region 3 - South Sound", "Child Care Center",
            ),
        ).lastrowid

        assessment_id = self.conn.execute(
            """
            INSERT INTO assessments (
                assessment_name, facility_id, facility_identifier,
                external_system, assessment_date, visit_date, inspection_type,
                assessor, status, external_case_number, external_inspection_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                assessment_name, facility_id, "FAC-008742", "Compass",
                assessment_date, visit_date, "Annual Monitoring Visit",
                "Ada Lovelace", "draft", "CMP-2026-00418211111",
                "INS-2026-0714-22",
            ),
        ).lastrowid
        self.conn.commit()
        return assessment_id