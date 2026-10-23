"""Check that committed generated artifacts match the trusted generator.

The generator is the default-branch code running this check. The spec and the
committed table are read from the evaluated revision as data; nothing from that
revision is executed. A match shows only that the table is exactly what this
generator produces from that spec. It does not review the spec's intent.
"""

from __future__ import annotations

from typing import Callable

from .contract import ContractError
from .route_matrix import GENERATOR, MAX_SPEC_BYTES, generate

CHECK_ID = "generated-artifacts-reproducible"
CLAIM_ID = "generated-artifacts"
SPEC_PATH = "evaluation/route-matrix-spec.json"
OUTPUT_PATH = "evaluation/generated/route-matrix.json"
GENERATED_PATHS = (SPEC_PATH, OUTPUT_PATH)
MAX_OUTPUT_BYTES = 4_000_000
CHECK_SCOPE = (
    f"Byte comparison of {OUTPUT_PATH} with the default-branch "
    f"{GENERATOR['name']} {GENERATOR['version']} output for {SPEC_PATH} at the evaluated revision. "
    "This shows the committed table is reproducible from its spec; it does not review what the spec selects."
)


def _first_difference(expected: bytes, actual: bytes) -> int:
    expected_lines = expected.split(b"\n")
    actual_lines = actual.split(b"\n")
    for number, (left, right) in enumerate(zip(expected_lines, actual_lines), start=1):
        if left != right:
            return number
    return min(len(expected_lines), len(actual_lines)) + 1


def build_generated_artifacts_check(read: Callable[[str, int], bytes | None], revision: str) -> dict[str, object]:
    """Regenerate from the revision's spec and compare with its committed table.

    `read(path, maximum)` returns the file at `revision`, or None when it is
    missing or larger than `maximum` bytes.
    """
    status = "NOT_RUN"
    spec = read(SPEC_PATH, MAX_SPEC_BYTES)
    committed = read(OUTPUT_PATH, MAX_OUTPUT_BYTES)
    if spec is None or committed is None:
        details = "NOT_RUN: spec or generated table is missing or exceeds its size limit"
    else:
        try:
            expected = generate(spec)
        except ContractError as exc:
            details = f"NOT_RUN: spec rejected: {exc}"
        else:
            if committed == expected:
                status = "PASS"
                details = "PASS: committed table is byte-identical to the regenerated table"
            else:
                status = "FAIL"
                details = (f"FAIL: committed table differs from the regenerated table "
                           f"starting at line {_first_difference(expected, committed)}")
    return {
        "id": CHECK_ID,
        "claim_id": CLAIM_ID,
        "status": status,
        "revision": revision,
        "source": dict(GENERATOR),
        "scope": CHECK_SCOPE,
        "artifact_ref": f"git-object:{revision}:{OUTPUT_PATH}" if committed is not None else None,
        "details": details,
    }
