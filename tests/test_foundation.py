"""
Verification Test Suite for Aegis-Ops Foundation and Configuration Layer.

Verifies fail-fast configuration startup validation, custom JSON logging formats, 
secret masking, and overall package exports using isolated python processes.
"""

import json
import os
import subprocess
import sys
import unittest


class TestAegisOpsFoundation(unittest.TestCase):
    """
    Unit tests targeting configuration boundary security, validation, and JSON logging.
    """

    def test_fail_fast_missing_config(self) -> None:
        """
        Assert that importing configuration without mandatory environment variables
        fails fast by exiting with code 1 and emitting structured JSON to stderr.
        """
        # Isolate environment by removing potential pre-configured environment credentials
        isolated_env = os.environ.copy()
        isolated_env.pop("GROQ_API_KEY", None)
        isolated_env.pop("NOTION_TOKEN", None)
        isolated_env.pop("NOTION_DATABASE_ID", None)

        # Attempt to import settings within an isolated python process
        cmd = [sys.executable, "-c", "import config.settings"]
        process = subprocess.run(
            cmd,
            env=isolated_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Assert SystemExit(1) was triggered
        self.assertEqual(process.returncode, 1)

        # Verify stderr output has proper structured JSON and custom levels
        try:
            log_output = json.loads(process.stderr.strip())
            self.assertEqual(log_output["level"], "CRITICAL")
            self.assertEqual(log_output["module"], "settings")
            self.assertIn("validation failed", log_output["message"])
        except json.JSONDecodeError:
            self.fail(f"Telemetry stderr output was not valid JSON: '{process.stderr}'")

    def test_success_with_valid_config(self) -> None:
        """
        Assert that importing configuration succeeds with return code 0
        when all required variables are set, and attributes are parsed properly.
        """
        isolated_env = os.environ.copy()
        isolated_env["GROQ_API_KEY"] = "gsk_valid_test_api_key"
        isolated_env["NOTION_TOKEN"] = "secret_valid_test_notion_token"
        isolated_env["NOTION_DATABASE_ID"] = "valid_database_uuid"
        isolated_env["ENV"] = "production"
        isolated_env["LOG_LEVEL"] = "WARNING"

        script = (
            "from config.settings import settings; "
            "print(settings.ENV); "
            "print(settings.LOG_LEVEL)"
        )
        cmd = [sys.executable, "-c", script]
        process = subprocess.run(
            cmd,
            env=isolated_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        self.assertEqual(process.returncode, 0, f"Process execution failed: {process.stderr}")
        outputs = process.stdout.strip().split("\n")
        self.assertEqual(outputs[0].strip(), "production")
        self.assertEqual(outputs[1].strip(), "WARNING")

    def test_structured_logging_format(self) -> None:
        """
        Assert that the global Aegis-Ops logger formats stdout logs into valid single-line JSON.
        """
        isolated_env = os.environ.copy()
        isolated_env["GROQ_API_KEY"] = "gsk_valid_test_api_key"
        isolated_env["NOTION_TOKEN"] = "secret_valid_test_notion_token"
        isolated_env["NOTION_DATABASE_ID"] = "valid_database_uuid"
        isolated_env["LOG_LEVEL"] = "INFO"

        script = (
            "from config.settings import logger; "
            "logger.info('Aegis-Ops system diagnostic test message')"
        )
        cmd = [sys.executable, "-c", script]
        process = subprocess.run(
            cmd,
            env=isolated_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        self.assertEqual(process.returncode, 0)

        # Verify stdout output parsed successfully as JSON containing required telemetry keys
        try:
            log_output = json.loads(process.stdout.strip())
            self.assertEqual(log_output["level"], "INFO")
            self.assertEqual(log_output["message"], "Aegis-Ops system diagnostic test message")
            self.assertIn("timestamp", log_output)
            self.assertIn("module", log_output)
            self.assertIn("function", log_output)
        except json.JSONDecodeError:
            self.fail(f"Logger stdout output was not valid JSON: '{process.stdout}'")

    def test_secrets_masked_in_settings_serialization(self) -> None:
        """
        Assert that sensitive credential values are masked when serialized or printed as string.
        """
        isolated_env = os.environ.copy()
        isolated_env["GROQ_API_KEY"] = "gsk_confidential_secret_value_12345"
        isolated_env["NOTION_TOKEN"] = "secret_confidential_secret_value_67890"
        isolated_env["NOTION_DATABASE_ID"] = "database_id"

        script = (
            "from config.settings import settings; "
            "print(str(settings))"
        )
        cmd = [sys.executable, "-c", script]
        process = subprocess.run(
            cmd,
            env=isolated_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        self.assertEqual(process.returncode, 0)
        output = process.stdout.strip()
        self.assertNotIn("gsk_confidential_secret_value_12345", output)
        self.assertNotIn("secret_confidential_secret_value_67890", output)
        self.assertIn("**********", output)


if __name__ == "__main__":
    unittest.main()
