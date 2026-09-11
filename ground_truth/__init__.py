"""Ground truth for evaluation only.

This package is deliberately isolated. It is imported by exactly one module,
``experiment.evaluation.metrics``. No observer, reconstructor or detection rule
may import it, and ``tests/test_ground_truth_isolation.py`` enforces that both
statically and at runtime.

The manifests describe the *intended observable trajectory* of each deterministic
scenario, authored from the scenario design rather than from any reconstruction
output.
"""

from ground_truth.loader import GroundTruth, load_ground_truth

__all__ = ["GroundTruth", "load_ground_truth"]
