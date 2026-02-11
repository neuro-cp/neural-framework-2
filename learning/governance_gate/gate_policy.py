class GovernanceGatePolicy:
    '''
    Pure governance gate policy.

    Approves only structurally clean governance records.

    Contract:
    - Pure
    - Deterministic
    - No mutation
    - No runtime access
    '''

    def compute(self, record=None):
        record = record or {}

        fragility = record.get("fragility_index", 0)
        was_clamped = record.get("was_clamped", False)

        if fragility > 0:
            return {
                "approved": False,
                "reason": "fragility_detected",
            }

        if was_clamped:
            return {
                "approved": False,
                "reason": "adjustment_clamped",
            }

        return {
            "approved": True,
            "reason": "structurally_clean",
        }
