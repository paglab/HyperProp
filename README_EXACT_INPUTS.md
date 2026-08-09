# Chapter 1: exact input organization for the three public analysis scripts

The package is aligned with the processed objects/files already used in the
original project scripts. It does NOT require raw hyperspectral imagery,
radiance cubes, spectral response functions, calibration-panel measurements,
GNSS/IMU, GCP/RTK, or proprietary preprocessing files.

## Folder structure

chapter1_release/
|
|-- 01_reflectance_analysis.py
|-- 02_vi_mixed_effects.py
|-- 03_rf_trait_retrieval.py
|
|-- data/
|   |
|   |-- wavelength_ref.npy
|   |
|   |-- reflectance/
|   |   |-- data_col_20250429.npz
|   |   |-- data_col_20250531.npz
|   |   |-- data_col_20250612.npz
|   |   `-- data_col_20250625.npz
|   |
|   |-- vi/
|   |   |-- 0429/VIs.pkl
|   |   |-- 0531/VIs.pkl
|   |   |-- 0612/VIs.pkl
|   |   `-- 0625/VIs.pkl
|   |
|   `-- rf/
|       |-- model_spectra.pkl
|       |-- LMA.xlsx
|       |-- LAI.xlsx
|       |-- LNC.xlsx
|       `-- Nitrogen.xlsx
|
`-- outputs/
    |-- reflectance/
    |-- vi/
    `-- rf/

======================================================================
1. REFLECTANCE ANALYSIS
======================================================================

Files you ALREADY have:
- wavelength_ref.npy
- data_col_YYYYMMDD.npz

Each .npz needs only the existing keys:
- ref
- RTM
- ELC
- ELC3

The wavelength vector is read separately from:
data/wavelength_ref.npy

No plot IDs are required. The code uses the row order as Plot_Index = 1..N.

Run:
    python 01_reflectance_analysis.py

Outputs:
- outputs/reflectance/spectral_metrics_by_plot.csv
- outputs/reflectance/spectral_metrics_summary.csv

======================================================================
2. VI + MIXED-EFFECTS ANALYSIS
======================================================================

Files you ALREADY have:
- VIs.pkl for each date

Copy them into:
- data/vi/0429/VIs.pkl
- data/vi/0531/VIs.pkl
- data/vi/0612/VIs.pkl
- data/vi/0625/VIs.pkl

The script assumes the exact original structure:
data[VI] -> numpy array with shape (4, N)

Rows:
0 = Reference
1 = RTM
2 = ELC
3 = ELC3

The script converts the original dictionaries to a long table internally,
calculates absolute errors, and fits:
Absolute_Error ~ Method * Period + (1 | Plot)

Run:
    python 02_vi_mixed_effects.py

Outputs:
- outputs/vi/vi_values_long.csv
- outputs/vi/vi_absolute_errors_long.csv
- outputs/vi/mixed_effects_tableVI.csv
- outputs/vi/mixed_model_<VI>.txt

======================================================================
3. RF TRAIT RETRIEVAL
======================================================================

The original project constructs the model-ready nested dictionary in memory:
- LAI_rfl    (all selected bands), or
- rfl_nir    (VNIR), or
- rfl_swir   (SWIR)

You do NOT need to release the raw files used to construct this dictionary.
For the public demo, save the exact model input once.

At the point in the original code AFTER LAI_rfl/rfl_nir/rfl_swir has been made:

    import pickle

    with open("model_spectra.pkl", "wb") as f:
        pickle.dump(rfl_swir, f)

Replace rfl_swir with LAI_rfl or rfl_nir depending on which spectral domain
you want the public demo to reproduce.

Copy the result to:
    data/rf/model_spectra.pkl

The pickle keeps the exact original structure:
{
    "RTM":  {"20250531": X, "20250612": X, "20250625": X},
    "ELC":  {"20250531": X, "20250612": X, "20250625": X},
    "ELC3": {"20250531": X, "20250612": X, "20250625": X}
}

You also use these files already:
- LMA.xlsx
- LAI.xlsx
- LNC.xlsx
- Nitrogen.xlsx

Copy them to data/rf/.

Important:
The date column names in the Excel files must match:
20250531, 20250612, 20250625

The script uses the row order exactly as in the original modelling code.
No additional metadata CSV is required.

wavelength_ref.npy is OPTIONAL for Script 3.
If its length matches the model-ready spectral matrix, real wavelengths are
written to the feature-importance file; otherwise Band_1, Band_2, ... are used.

Run:
    python 03_rf_trait_retrieval.py

Outputs:
- outputs/rf/rf_out_of_fold_predictions.csv
- outputs/rf/rf_overall_metrics.csv
- outputs/rf/rf_fold_metrics.csv
- outputs/rf/rf_fold_uncertainty_summary.csv
- outputs/rf/rf_feature_importance.csv

======================================================================
WHAT TO PUBLICLY UPLOAD
======================================================================

Minimum demo package:

Reflectance:
- wavelength_ref.npy
- 2-4 data_col_YYYYMMDD.npz files, possibly with only a small subset of rows

VI:
- matching VIs.pkl files for those dates, possibly subset to the same plots

RF:
- model_spectra.pkl containing only the model-ready processed spectra
- four trait tables, preferably anonymized/subset if the complete data cannot
  be released

No upstream raw/preprocessing data are required for these scripts.
