import unittest

from ssh_gpu_checker.inspect import (
    classify_ssh_failure,
    parse_nvidia_smi_csv,
    parse_nvidia_smi_output,
)


class ParseNvidiaSmiCsvTests(unittest.TestCase):
    def test_parses_rows_and_computes_free_memory(self) -> None:
        rows = parse_nvidia_smi_csv("0, NVIDIA A100, 81920, 1024, 7\n")
        self.assertEqual(rows[0].free_memory_mb, 80896)
        self.assertEqual(rows[0].gpu_index, "0")

    def test_parses_na_utilization_as_unknown(self) -> None:
        rows = parse_nvidia_smi_csv("0, NVIDIA A100, 81920, 1024, [N/A]\n")
        self.assertIsNone(rows[0].utilization_gpu_percent)

    def test_classifies_missing_binary(self) -> None:
        self.assertEqual(
            classify_ssh_failure(127, "bash: nvidia-smi: command not found"),
            "no_nvidia_smi",
        )

    def test_parses_extended_gpu_and_process_rows(self) -> None:
        output = """__GPU__
0, GPU-abc, NVIDIA RTX 4090, 49140, 1024, [N/A], 42
__PROC__
GPU-abc, 1234, 768, alice
"""
        rows = parse_nvidia_smi_output(output)
        self.assertEqual(rows[0].uuid, "GPU-abc")
        self.assertEqual(rows[0].temperature_celsius, 42)
        self.assertIsNone(rows[0].utilization_gpu_percent)
        self.assertEqual(rows[0].processes[0].pid, 1234)
        self.assertEqual(rows[0].processes[0].username, "alice")

    def test_rejects_malformed_gpu_row(self) -> None:
        with self.assertRaisesRegex(ValueError, "GPU row"):
            parse_nvidia_smi_output("__GPU__\nnot,enough,fields\n__PROC__\n")

    def test_rejects_malformed_process_row(self) -> None:
        with self.assertRaisesRegex(ValueError, "process row"):
            parse_nvidia_smi_output(
                "__GPU__\n0,GPU-a,A100,1000,0,0,40\n"
                "__PROC__\nGPU-a,1234\n"
            )

    def test_treats_bracketed_gpu_status_as_unknown_metric(self) -> None:
        rows = parse_nvidia_smi_output(
            "__GPU__\n"
            "3,GPU-reset,NVIDIA RTX 4090,49140,1,[N/A],[GPU requires reset]\n"
            "__PROC__\n"
        )

        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].utilization_gpu_percent)
        self.assertIsNone(rows[0].temperature_celsius)


if __name__ == "__main__":
    unittest.main()
