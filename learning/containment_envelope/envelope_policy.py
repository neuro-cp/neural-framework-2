class ContainmentEnvelopePolicy:
    '''
    Pure containment envelope policy.

    Computes allowable calibration magnitude
    based on fragility index.

    Contract:
    - Pure
    - Deterministic
    - No mutation
    - No runtime access
    '''

    def compute(self, fragility=None, max_adjustment=10):
        fragility = fragility or {}

        fragility_index = fragility.get("fragility_index", 0)

        if fragility_index <= 0:
            allowed = max_adjustment
        else:
            allowed = max(0, max_adjustment - fragility_index)

        return {
            "allowed_adjustment": allowed,
            "fragility_index": fragility_index,
            "max_adjustment": max_adjustment,
        }
