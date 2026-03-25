import cdsapi

dataset = "reanalysis-era5-single-levels-timeseries"
request = {
    "variable": [
        "2m_dewpoint_temperature",
        "10m_wind_gust_since_previous_post_processing",
        "mean_sea_level_pressure",
        "skin_temperature",
        "surface_pressure",
        "surface_solar_radiation_downwards",
        "sea_surface_temperature",
        "surface_thermal_radiation_downwards",
        "2m_temperature",
        "total_precipitation",
        "10m_u_component_of_wind",
        "10m_v_component_of_wind",
        "100m_u_component_of_wind",
        "100m_v_component_of_wind",
        "mean_wave_direction",
        "mean_wave_period",
        "significant_height_of_combined_wind_waves_and_swell"
    ],
    "location": {"longitude": 19.25, "latitude": 31},
    "date": ["2000-01-01/2026-03-17"],
    "data_format": "csv"
}

client = cdsapi.Client()
client.retrieve(dataset, request).download()
