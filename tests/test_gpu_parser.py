import unittest

from ssh_gpu_checker.inspect import classify_ssh_failure, parse_nvidia_smi_csv


class ParseNvidiaSmiCsvTests(unittest.TestCase):
    def test_parses_rows_and_computes_free_memory(self) -> None:
        rows = parse_nvidia_smi_csv("0, NVIDIA A100, 81920, 1024, 7\n")
        self.assertEqual(rows[0].free_memory_mb, 80896)
        self.assertEqual(rows[0].gpu_index, "0")

    def test_classifies_missing_binary(self) -> None:
        self.assertEqual(
            classify_ssh_failure(127, "bash: nvidia-smi: command not found"),
            "no_nvidia_smi",
        )


if __name__ == "__main__":
    unittest.main()
