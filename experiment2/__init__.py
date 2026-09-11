"""Experiment 002 - blinded investigator reconstruction.

Experiment 001 measured provenance-edge recovery against data-flow-shaped ground
truth, using a data-flow-shaped observer. That is its strongest threat to
validity: the outcome measure and the treatment share an ontology.

Experiment 002 replaces the outcome. Independent investigators receive blinded
telemetry packages and answer fixed operational incident-response questions. The
question is no longer "how many edges were recovered" but "did the investigator
correctly understand what happened".

Nothing here assumes provenance telemetry helps. Three outcomes are equally
reportable: it helps, it does nothing, or it makes investigators confidently
wrong.
"""

__version__ = "0.1.0"
