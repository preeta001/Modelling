def generate_recommendations(current_state: dict, optimal_state: dict, limits: dict) -> dict:
    """
    Layer 3: Recommendation ranking
    """
    recs = []
    
    # Layer 1 Rules
    if current_state.get('WI_peak', 0.0) > limits.get('WI_crit', 1.05):
        recs.append({
            'type': 'CRITICAL',
            'message': 'Overwetting risk detected.',
            'action': 'Decrease spray rate or increase inlet temp/airflow.'
        })
        
    if current_state.get('T_bed_peak', 0.0) > limits.get('T_dcmp_C', 60.0):
        recs.append({
            'type': 'CRITICAL',
            'message': 'Thermal degradation risk detected.',
            'action': 'Decrease inlet temp or increase spray rate.'
        })
        
    # Layer 2 Optimizer Suggestions
    spray_diff = optimal_state.get('spray_rate_g_min_gun', 0) - current_state.get('spray_rate_g_min_gun', 0)
    if abs(spray_diff) > 5.0:
        verb = "Increase" if spray_diff > 0 else "Decrease"
        recs.append({
            'type': 'OPTIMIZATION',
            'message': 'Suboptimal spray rate.',
            'action': f'{verb} spray rate by {abs(spray_diff):.1f} g/min/gun.'
        })
        
    return {
        'current_assessment': 'High Risk' if any(r['type'] == 'CRITICAL' for r in recs) else 'Nominal',
        'recommendations': recs
    }
