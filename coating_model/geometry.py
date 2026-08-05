from dataclasses import dataclass
import math

@dataclass
class Equipment:
    name: str
    diameter_m: float
    length_m: float
    volume_L: float
    opening_diameter_m: float
    guns: int
    nozzle_diameter_mm: float
    gun_spacing_m: float
    airflow_min_cfm: float
    airflow_max_cfm: float
    rpm_min: float
    rpm_max: float
    spray_max_g_min_gun: float
    HLF_kW_K: float

    @property
    def aspect_ratio(self) -> float:
        return self.length_m / self.diameter_m

def estimate_bed_surface_area(equip: Equipment, batch_load_kg: float, bulk_density_kg_m3: float = 700.0) -> float:
    """
    Estimate the exposed surface area of the tablet bed.
    A very simplified chord-based geometric model.
    """
    bed_volume_m3 = batch_load_kg / bulk_density_kg_m3
    pan_volume_m3 = equip.volume_L / 1000.0
    
    occupancy_fraction = bed_volume_m3 / pan_volume_m3
    
    # Simple heuristic: area proportional to diameter * length * some function of fill
    # In a real model, this uses the circular segment geometry
    # A_bed = L * D * sin(theta_c / 2)
    # where theta_c is the chord angle
    
    # Rough approximation for 10-30% fill
    fill_factor = min(0.5, max(0.1, occupancy_fraction))
    # For a circle, chord length approx D * sqrt(fill) for small fills
    chord_length = equip.diameter_m * math.sqrt(fill_factor * 2.0)
    
    A_bed = chord_length * equip.length_m
    return A_bed
