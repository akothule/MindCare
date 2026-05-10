from mindcare.llm import apply_soft_empathy_calibration


def test_soft_empathy_calibration_includes_cues_and_low_routing_instruction() -> None:
    out = apply_soft_empathy_calibration("Hello", ["hopelessness_cue"])
    assert out.startswith("Hello")
    assert "LOW" in out
    assert "hopelessness_cue" in out
    assert "988 resource" in out.lower() or "hotline" in out.lower()
