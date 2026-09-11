"""Evaluator-only ground truth for Experiment 002.

Investigators never see any of this. Only the scoring and metrics layers of
Experiment 002 may import it, enforced by
``tests/test_experiment2_isolation.py``.

The manifests describe *factual properties of each incident* - what the task was,
what the assistant did, which inputs are relevant, what a defensible answer looks
like. They are deliberately written in ordinary incident-response language. No
manifest field asks whether an investigator recovered a graph, an edge, or a
lineage relationship, and a test asserts that no alias in any manifest contains
provenance vocabulary.
"""

from evaluator_manifests.loader import EvaluatorManifest, load_manifest, manifest_ids

__all__ = ["EvaluatorManifest", "load_manifest", "manifest_ids"]
