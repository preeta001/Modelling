def check_validity_envelope(inputs: dict, limits: dict, validated_ranges: dict) -> dict:
    """
    Model Validity Envelope / Abstention Logic.
    """
    warnings = []
    extrapolations = []
    
    for param, val in inputs.items():
        if param in limits:
            if isinstance(limits[param], (list, tuple)) and len(limits[param]) == 2:
                if val < limits[param][0] or val > limits[param][1]:
                    warnings.append(f"{param} ({val}) is outside safe limits {limits[param]}")
            elif isinstance(limits[param], (int, float)):
                if val > limits[param]:
                    warnings.append(f"{param} ({val}) exceeds max limit {limits[param]}")
                    
        if param in validated_ranges:
            if val < validated_ranges[param][0] or val > validated_ranges[param][1]:
                extrapolations.append(f"{param} ({val}) is outside validated range {validated_ranges[param]}. Model is extrapolating.")
                
    status = "VALID"
    if extrapolations:
        status = "EXTRAPOLATION"
    if warnings:
        status = "ABSTAIN" # Too dangerous/invalid to run
        
    return {
        'status': status,
        'warnings': warnings,
        'extrapolations': extrapolations
    }
