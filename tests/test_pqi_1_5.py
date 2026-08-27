"""PQI 1 through 5 rendering, scoring, persistence, and validation."""

import io
import json
import unittest
from unittest.mock import patch

from app import app, save_assignment_draft, set_current_assessment
from constants import INCLUDED_COMPONENTS, REGULATION_SET_NAME, REGULATION_SET_VERSION
from services.formatters import round_percentage_half_up
from tests.test_support import AssessmentTestCase


class PqiOneToFiveTests(AssessmentTestCase):
    """PQI 1 through 5 rendering, scoring, persistence, and validation."""

    def test_save_pqi1_persists_nested_json(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi1",
            json={
                "certified_teaching_staff": 6,
                "total_teaching_staff": 12,
            },
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()

        self.assertIsNotNone(saved_row)
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi1"]["score"], 2)
        self.assertEqual(saved_findings["pqi1"]["certified_teaching_staff"], 6)
        self.assertEqual(saved_findings["pqi1"]["total_teaching_staff"], 12)


    def test_complete_pqi1_marks_entry_complete(self):
        assessment_id = self.insert_assessment()

        response = self.client.post(
            "/api/assessments/pqi1",
            json={
                "assessment_id": assessment_id,
                "certified_teaching_staff": 6,
                "total_teaching_staff": 12,
                "complete": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        self.assertTrue(json.loads(saved_row[0])["pqi1"]["complete"])


    def test_save_pqi2_persists_nested_json(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi2",
            json={
                "complete": True,
                "responses": {
                    "2.1": "yes",
                    "2.2": "yes",
                    "2.3": "yes",
                    "2.4": "yes",
                    "2.5": "yes",
                    "2.6": "yes",
                    "2.7": "yes",
                    "2.8": "yes",
                    "2.9": "yes",
                    "2.10": "no",
                    "2.11": "no",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()

        self.assertIsNotNone(saved_row)
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi2"]["score"], 4)
        self.assertEqual(saved_findings["pqi2"]["yes_count"], 9)
        self.assertEqual(saved_findings["pqi2"]["question_count"], 11)
        self.assertEqual(saved_findings["pqi2"]["responses"]["2.10"], "no")


    def test_save_pqi2_persists_optional_note(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi2",
            json={
                "complete": True,
                "responses": {
                    "2.1": "yes",
                    "2.2": "yes",
                    "2.3": "yes",
                    "2.4": "yes",
                    "2.5": "yes",
                    "2.6": "yes",
                    "2.7": "yes",
                    "2.8": "yes",
                    "2.9": "yes",
                    "2.10": "no",
                    "2.11": "no",
                },
                "optional_note": "Classroom materials were refreshed to support the new environmental goals.",
            },
        )

        self.assertEqual(response.status_code, 200)

        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi2"]["optional_note"], "Classroom materials were refreshed to support the new environmental goals.")

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")
        self.assertIn('id="pqi2-optional-note"', rendered)
        self.assertIn("Classroom materials were refreshed to support the new environmental goals.", rendered)


    def test_save_pqi2_complete_requires_all_answers(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi2",
            json={
                "complete": True,
                "responses": {
                    "2.1": "yes",
                    "2.2": "no",
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["message"], "Answer all PQI 2 questions before completing")


    def test_save_pqi5_persists_nested_json(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi5",
            json={
                "complete": True,
                "responses": {
                    "5.1": "yes",
                    "5.2": "yes",
                    "5.3": "no",
                },
            },
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()

        self.assertIsNotNone(saved_row)
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi5"]["base_points"], 3)
        self.assertEqual(saved_findings["pqi5"]["bonus_point"], 0)
        self.assertEqual(saved_findings["pqi5"]["score"], 3)
        self.assertEqual(saved_findings["pqi5"]["responses"]["5.3"], "no")


    def test_save_pqi5_complete_requires_all_answers(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi5",
            json={
                "complete": True,
                "responses": {
                    "5.1": "yes",
                },
            },
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["message"], "Answer all PQI 5 questions before completing")


    def test_displayed_percentages_round_half_up_to_whole_number(self):
        self.assertEqual(round_percentage_half_up(66.5), 67)
        self.assertEqual(round_percentage_half_up(66.49), 66)
        self.assertEqual(round_percentage_half_up(33.3333333333), 33)
        self.assertEqual(round_percentage_half_up(66.6666666667), 67)


    def test_pqi4_renders_and_uses_static_percentage_bands(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")
        self.assertIn('id="pqi4-card"', rendered)
        self.assertIn("Opportunities for Staff and Families to Get to Know Each Other", rendered)
        self.assertIn("meets their diverse needs", rendered)

        cases = [
            ({"4.1": "no", "4.2": "no", "4.3": "no"}, 1),
            ({"4.1": "yes", "4.2": "no", "4.3": "no"}, 2),
            ({"4.1": "yes", "4.2": "yes", "4.3": "no"}, 3),
            ({"4.1": "yes", "4.2": "yes", "4.3": "yes"}, 4),
        ]
        for responses, expected_score in cases:
            response = self.client.post(
                "/api/assessments/pqi4",
                json={"complete": True, "responses": responses},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["score"], expected_score)

        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi4"]["score"], 4)
        self.assertEqual(saved_findings["pqi4"]["responses"]["4.3"], "yes")


    def test_save_pqi4_persists_optional_note(self):
        assessment_id = self.insert_assessment()

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        response = self.client.post(
            "/api/assessments/pqi4",
            json={
                "assessment_id": assessment_id,
                "complete": True,
                "responses": {"4.1": "yes", "4.2": "yes", "4.3": "yes"},
                "optional_note": "Staff were introduced to family support resources during orientation.",
            },
        )

        self.assertEqual(response.status_code, 200)

        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi4"]["optional_note"], "Staff were introduced to family support resources during orientation.")

        rendered = self.client.get("/screens/pqi-findings-entry").data.decode("utf-8")
        self.assertIn('id="pqi4-optional-note"', rendered)
        self.assertIn("Staff were introduced to family support resources during orientation.", rendered)


    def test_save_pqi3_persists_and_reloads_records_and_notes(self):
        assessment_id = self.insert_assessment()

        records = {
            f"record {index}": {
                "emergent_curriculum": "yes" if index == 1 else "no",
                "co_learning": "yes",
                "documented_learning_future_planning": "yes",
                "notes": f"Evidence note {index}",
            }
            for index in range(1, 11)
        }
        response = self.client.post(
            "/api/assessments/pqi3",
            json={"assessment_id": assessment_id, "records": records, "completed": True},
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertTrue(saved_findings["pqi3"]["completed"])
        self.assertEqual(saved_findings["pqi3"]["record 1"]["emergent_curriculum"], "yes")
        self.assertEqual(saved_findings["pqi3"]["record 1"]["notes"], "Evidence note 1")

        with self.client.session_transaction() as session:
            session["current_assessment_id"] = assessment_id

        rendered = self.client.get("/screens/pqi3").get_data(as_text=True)
        self.assertIn('value="Evidence note 1"', rendered)
        self.assertIn('data-emergent_curriculum="yes"', rendered)
        self.assertIn("PQI 3 marked as complete", rendered)


    def test_save_pqi3_accepts_numeric_record_keys(self):
        assessment_id = self.insert_assessment()
        records = {
            str(index): {
                "emergent_curriculum": "yes" if index == 1 else "no",
                "co_learning": "yes",
                "documented_learning_future_planning": "yes",
                "notes": f"Numeric-key note {index}",
            }
            for index in range(1, 11)
        }

        response = self.client.post(
            "/api/assessments/pqi3",
            json={"assessment_id": assessment_id, "records": records, "completed": True},
        )

        self.assertEqual(response.status_code, 200)
        saved_row = self.conn.execute(
            "SELECT pqi_findings FROM assessments WHERE id = ?",
            (assessment_id,),
        ).fetchone()
        saved_findings = json.loads(saved_row[0])
        self.assertEqual(saved_findings["pqi3"]["record 1"]["notes"], "Numeric-key note 1")
        self.assertTrue(saved_findings["pqi3"]["completed"])


    def test_save_pqi3_rejects_disabled_indicator(self):
        assessment_id = self.insert_assessment()
        with patch(
            "routes.build_pqi_access_context",
            return_value={"pqi_allowed": {"3": False}},
        ):
            response = self.client.post(
                "/api/assessments/pqi3",
                json={"assessment_id": assessment_id, "records": {}, "completed": True},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("PQI 3 is not available", response.get_json()["message"])



