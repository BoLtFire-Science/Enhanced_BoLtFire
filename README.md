# Enhanced_BoLtFire_Code

Climate change is expected to change both fire susceptibility and lightning activity in global boreal forests. The mechanics governing lighting-ignited wildfire (LIW) ignition remains, however, unclear, making predictions of future fire regions on a global boreal scale challenging. Here we examine short-term temporal impacts of weather on ignition probability using a novel dataset on LIWs in a quasi-experimental design of ignition and non-ignition lightning pairs. Specifically, our dataset comprises of 5,251 lightning pairs coupled with temperature, precipitation, relative humidity, lightning characteristics (polarity, multiplicity, duration, and peak current - available for scientific use from the ENTLN) and net primary productivity. This dataset provides new opportunities to model ignition dynamics of wildfires and offers deeper insights into lightning-driven fire activity.

Dataset can be found at: 10.5281/zenodo.19858357

The end python product is a csv file containing the below. The end R-Studio code provides the final model results. 

Dataset:
FireID: Unique identifier for the fire (LIW and NonLIW versions). Original LIW from the BoLtFire database

LIWType: Type of event: LIW (Lightning Ignited Wildfire) or NonLIW

offset: Days relative to the lightning event (0 = day of event)

holdover: Days between lightning event and fire observation 

FireSize: Size of the fire event (see methodology of Engle et al., 2025A) 

fire_type: Binary indicator: 1 (fire), 0 (no fire)

continent: North America or Eurasia

year: Year of the lightning event 

LC_Name: Land cover name (derived from MODIS/Terra+Aqua Land Cover Type Yearly L3 Global 500m (MCD12Q1))

LCDN: Land cover number (derived from MODIS/Terra+Aqua Land Cover Type Yearly L3 Global 500m (MCD12Q1))

EcoName: Ecoregion name (Olson et al., 2001)

NPP: Net Primary Production (MOD17A3HGF.061 Terra)

tp_mean: mean total precipitation (mm) for the 24-hour offset day (calculated from ERA5-Land)

t2m_mean: mean maximum 2m temperature (°C) for the 24-hour offset day (calculated from ERA5-Land)

ws_mean: mean maximum wind speed (m/s) for the 24-hour offset day (calculated per Pettinari & Chuvieco, 2017)

rh_mean: Mean relative humidity (%) for the 24-hour offset day (calculated per Wanielista et al., 1997)


Engle, B., & Bratoev, I. (2025). BoLtFire Code Release version 1 (Version v1.0.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.15425620

Engle, B., Bratoev, I., Crowley, M. A., Zhu, Y., & Senf, C. (2025A). Distribution and Characteristics of Lightning-Ignited Wildfires in Boreal Forests – the BoLtFire database (3.0) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.14940326

Engle, B., Bratoev, I., Crowley, M. A., Zhu, Y., & Senf, C. (2025B). Distribution and characteristics of lightning-ignited wildfires in boreal forests – the BoLtFire database. Earth System Science Data, 17, 2249–2276. https://doi.org/10.5194/essd-17-2249-2025

Olson, D. M., Dinerstein, E., Wikramanayake, E. D., Burgess, N. D., Powell, G. V. N., Underwood, E. C., D'Amico, J. A., Itoua, I., Strand, H. A., Morrison, J. C., Loucks, C. J., Allnutt, T. F., Ricketts, T. H., Kura, Y., Lamoreux, J. F., Wettengel, W. W., Hedao, P., & Kassem, K. R. (2001). Terrestrial Ecoregions of the World: A New Map of Life on Earth. BioScience, 51(11), 933–938. https://doi.org/10.1641/0006-3568(2001)051[0933:TEOTWA]2.0.CO;2

Pettinari, M., & Chuvieco, E. (2017). Fire Behavior Simulation from Global Fuel and Climatic Information. Forests, 8(6), 179. https://doi.org/10.3390/f8060179

Wanielista, M. P., Kersten, R., & Ealgin, R. (1997). Hydrology: Water Quantity and Quality Control (2nd ed.). John Wiley & Sons.
