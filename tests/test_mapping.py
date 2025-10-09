"""Unit tests for the mapping helpers and transform plumbing."""

from __future__ import annotations

import pytest

from roomlens import mapping


def _build_mapping(transform: str | None = None):
    feature_cfg = {"map_to": {"axis": "demo"}}
    if transform:
        feature_cfg["transform"] = transform
    return {
        "sensors": {
            "mic": {
                "enabled": True,
                "features": {
                    "rms": feature_cfg,
                },
            }
        }
    }


def test_log10_clamp_transform_scales_decibels():
    mapping_cfg = _build_mapping("log10_clamp")
    frame = {"mic_rms": 10 ** (-30 / 20)}
    axes = mapping.apply_mapping(frame, mapping_cfg)
    assert pytest.approx(axes["demo"], rel=1e-6) == 0.5


def test_softclip_transform_eases_high_values():
    mapping_cfg = _build_mapping("softclip(threshold=0.5,slope=6)")
    # Below the threshold we should preserve the input.
    axes_low = mapping.apply_mapping({"mic_rms": 0.3}, mapping_cfg)
    assert pytest.approx(axes_low["demo"], rel=1e-6) == 0.3

    axes_high = mapping.apply_mapping({"mic_rms": 0.9}, mapping_cfg)
    assert axes_high["demo"] < 0.9
    assert axes_high["demo"] > 0.5


def test_inverse_exp_favors_values_below_centers():
    mapping_cfg = _build_mapping("inverse_exp(centers=[50, 120], k=1.2)")
    close = mapping.apply_mapping({"mic_rms": 30}, mapping_cfg)["demo"]
    mid = mapping.apply_mapping({"mic_rms": 80}, mapping_cfg)["demo"]
    far = mapping.apply_mapping({"mic_rms": 160}, mapping_cfg)["demo"]
    assert close > mid > far
    assert far == pytest.approx(0.0)


def test_unknown_transform_raises_value_error():
    mapping_cfg = _build_mapping("not_a_real_transform")
    with pytest.raises(ValueError):
        mapping.apply_mapping({"mic_rms": 0.2}, mapping_cfg)


def test_source_field_prefers_first_available_key():
    mapping_cfg = {
        "sensors": {
            "mic": {
                "enabled": True,
                "features": {
                    "rms": {
                        "source": "primary|fallback",
                        "map_to": {"axis": "demo"},
                    }
                },
            }
        }
    }
    frame = {"fallback": 0.8}
    axes = mapping.apply_mapping(frame, mapping_cfg)
    assert axes["demo"] == pytest.approx(0.8)
