import os
import tempfile
import unittest

from config import _load_or_create_jwt_secret


class JwtSecretPersistenceTests(unittest.TestCase):
    def test_generated_secret_is_reused_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            secret_file = os.path.join(directory, ".jwt-secret")

            first = _load_or_create_jwt_secret(secret_file)
            second = _load_or_create_jwt_secret(secret_file)

            self.assertGreaterEqual(len(first), 32)
            self.assertEqual(first, second)

    def test_existing_secret_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            secret_file = os.path.join(directory, ".jwt-secret")
            expected = "stable-secret-" + ("x" * 40)
            with open(secret_file, "w", encoding="utf-8") as file:
                file.write(expected)

            self.assertEqual(_load_or_create_jwt_secret(secret_file), expected)


if __name__ == "__main__":
    unittest.main()
