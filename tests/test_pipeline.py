"""Unit tests for the shared Room Lens processing pipeline."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from roomlens import MappingPipeline, apply_mapping, demo_frame, load_mapping, validate_mapping_axes

ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = ROOT / "config" / "mapping.default.yaml"


class MappingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mapping = load_mapping(MAPPING_PATH)

    def test_mapping_validates(self) -> None:
        """The default mapping should declare axes for every feature."""

        # No exception = pass
        validate_mapping_axes(self.mapping)

    def test_apply_mapping_known_values(self) -> None:
        """Explicit frame values hit the expected axis ranges."""

        frame = {
            "mic_rms": 1.0,
            "mic_sc": 0.0,
            "hf": 0.0,
            "tof_motion": 0.5,
            "tof_near": 0.5,
            "lux": 1.0,
            "flicker": 0.0,
            "motion": 1,
        }
        axes = apply_mapping(frame, self.mapping)
        self.assertAlmostEqual(axes["grain_density"], 0.45, places=6)
        self.assertAlmostEqual(axes["filter_cutoff_hz"], 400.0, places=6)
        self.assertAlmostEqual(axes["distortion_drive"], 0.0, places=6)
        self.assertAlmostEqual(axes["fm_index"], 1.05, places=6)
        self.assertAlmostEqual(axes["pitch_cluster_width_cents"], 350.0, places=6)
        self.assertAlmostEqual(axes["reverb_mix"], 0.35, places=6)
        self.assertAlmostEqual(axes["delay_time_ms"], 90.0, places=6)
        self.assertAlmostEqual(axes["env_attack_ms"], 5.0, places=6)

    def test_pipeline_payload_matches_apply_mapping(self) -> None:
        """MappingPipeline should mirror :func:`apply_mapping`."""

        pipeline = MappingPipeline(self.mapping)
        frame = demo_frame(0.5)
        payload = pipeline.process_frame(frame)
        self.assertIn("axes", payload)
        self.assertEqual(payload["axes"], apply_mapping(frame, self.mapping))

    def test_prepare_osc_message_orders_axes(self) -> None:
        """OSC message payload should be deterministic for tests/hosts."""

        pipeline = MappingPipeline(self.mapping)
        frame = {
            "mic_rms": 0.2,
            "mic_sc": 0.7,
            "tof_motion": 0.3,
            "tof_near": 0.1,
            "lux": 0.5,
            "flicker": 0.4,
            "motion": 0,
        }
        payload = pipeline.process_frame(frame)
        address, args = pipeline.prepare_osc_message(payload)
        self.assertEqual(address, "/roomlens")
        # Arguments should be [axis, value, axis, value, ...] sorted by axis name.
        axes_in_args = [args[i] for i in range(0, len(args), 2)]
        self.assertEqual(sorted(axes_in_args), axes_in_args)
        # Values should serialize cleanly to JSON numbers (regression check).
        json.dumps(args)


if __name__ == "__main__":
    unittest.main()
