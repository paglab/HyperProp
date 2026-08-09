"""
03_rf_trait_retrieval.py

This script starts from ONE processed model-input file instead of raw UAV data.

You already create the model-ready dictionary in the original PLSR_model.py:
    LAI_rfl / rfl_nir / rfl_swir

For public release, save the chosen model-ready dictionary once as:
    data/rf/model_spectra.pkl

The pickle must contain the SAME nested structure:
{
    "RTM":  {date: ndarray(n_plots, n_bands), ...},
    "ELC":  {date: ndarray(n_plots, n_bands), ...},
    "ELC3": {date: ndarray(n_plots, n_bands), ...}
}

Other inputs are the same measured trait files already used by the project:
    data/rf/LMA.xlsx
    data/rf/LAI.xlsx
    data/rf/LNC.xlsx
    data/rf/Nitrogen.xlsx

Optional:
    data/wavelength_ref.npy

If wavelengths are supplied, feature-importance output includes wavelength.
If not, it uses Band_1, Band_2, ... only.
"""

from pathlib import Path
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import r2_score, mean_squared_error

DATA_DIR = Path("data")
RF_DIR = DATA_DIR / "rf"
OUTPUT_DIR = Path("outputs/rf")

MODEL_SPECTRA_FILE = RF_DIR / "model_spectra.pkl"
WAVELENGTH_FILE = DATA_DIR / "wavelength_ref.npy"

TRAIT_FILES = {
    "LMA": RF_DIR / "LMA.xlsx",
    "LAI": RF_DIR / "LAI.xlsx",
    "LNC": RF_DIR / "LNC.xlsx",
    "CNC": RF_DIR / "Nitrogen.xlsx",
}

DATES = ["20250531", "20250612", "20250625"]
METHODS = ["RTM", "ELC", "ELC3"]
N_SPLITS = 5
RANDOM_STATE = 42
N_ESTIMATORS = 100


def load_trait_tables():
    traits = {}
    for trait, path in TRAIT_FILES.items():
        df = pd.read_excel(path)
        # Preserve the same LMA transformation used in the original code.
        if trait == "LMA":
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            cols_to_scale = [c for c in numeric_cols if c != "Plot Number"]
            df[cols_to_scale] = df[cols_to_scale] * 10000
        traits[trait] = df
    return traits


def load_model_spectra():
    with open(MODEL_SPECTRA_FILE, "rb") as f:
        x_dict = pickle.load(f)
    return x_dict


def get_target(df, date):
    if date not in df.columns:
        raise KeyError(
            f"Trait table has no column '{date}'. Available: {list(df.columns)}"
        )
    return df[date].to_numpy(dtype=float)


def rmse(y_true, y_pred):
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    x_dict = load_model_spectra()
    trait_tables = load_trait_tables()

    if WAVELENGTH_FILE.exists():
        wavelengths = np.load(WAVELENGTH_FILE)
    else:
        wavelengths = None

    pred_rows = []
    overall_rows = []
    fold_rows = []
    importance_rows = []

    for date in DATES:
        # Same folds are generated once for a date and reused for all methods.
        first_method = METHODS[0]
        n_samples = np.asarray(x_dict[first_method][date]).shape[0]

        kf = KFold(
            n_splits=N_SPLITS,
            shuffle=True,
            random_state=RANDOM_STATE
        )
        folds = list(kf.split(np.arange(n_samples)))

        for trait, trait_df in trait_tables.items():
            y = get_target(trait_df, date)

            if len(y) != n_samples:
                raise ValueError(
                    f"{trait}-{date}: y has {len(y)} samples, spectra have {n_samples}"
                )

            for method in METHODS:
                X = np.asarray(x_dict[method][date], dtype=float)
                oof = np.full(n_samples, np.nan)
                fold_importances = []

                for fold_no, (train_idx, test_idx) in enumerate(folds, start=1):
                    model = RandomForestRegressor(
                        n_estimators=N_ESTIMATORS,
                        random_state=RANDOM_STATE
                    )
                    model.fit(X[train_idx], y[train_idx])
                    pred = model.predict(X[test_idx])
                    oof[test_idx] = pred
                    fold_importances.append(model.feature_importances_)

                    fold_rows.append({
                        "Date": date,
                        "Trait": trait,
                        "Method": method,
                        "Fold": fold_no,
                        "R2": r2_score(y[test_idx], pred),
                        "RMSE": rmse(y[test_idx], pred),
                    })

                overall_rows.append({
                    "Date": date,
                    "Trait": trait,
                    "Method": method,
                    "n": n_samples,
                    "R2": r2_score(y, oof),
                    "RMSE": rmse(y, oof),
                })

                for sample_idx, (yt, yp) in enumerate(zip(y, oof), start=1):
                    pred_rows.append({
                        "Date": date,
                        "Sample_Index": sample_idx,
                        "Trait": trait,
                        "Method": method,
                        "Measured": yt,
                        "Predicted": yp,
                    })

                mean_imp = np.mean(np.vstack(fold_importances), axis=0)
                for band_idx, imp in enumerate(mean_imp):
                    if wavelengths is not None and len(wavelengths) == len(mean_imp):
                        band_label = float(wavelengths[band_idx])
                    else:
                        band_label = band_idx + 1
                    importance_rows.append({
                        "Date": date,
                        "Trait": trait,
                        "Method": method,
                        "Band_or_Wavelength": band_label,
                        "Feature_Importance": imp,
                    })

    pred_df = pd.DataFrame(pred_rows)
    overall_df = pd.DataFrame(overall_rows)
    fold_df = pd.DataFrame(fold_rows)
    imp_df = pd.DataFrame(importance_rows)

    pred_df.to_csv(OUTPUT_DIR / "rf_out_of_fold_predictions.csv", index=False)
    overall_df.to_csv(OUTPUT_DIR / "rf_overall_metrics.csv", index=False)
    fold_df.to_csv(OUTPUT_DIR / "rf_fold_metrics.csv", index=False)

    fold_summary = fold_df.groupby(["Date", "Trait", "Method"], as_index=False).agg(
        R2_fold_mean=("R2", "mean"),
        R2_fold_SD=("R2", "std"),
        RMSE_fold_mean=("RMSE", "mean"),
        RMSE_fold_SD=("RMSE", "std"),
    )
    fold_summary.to_csv(
        OUTPUT_DIR / "rf_fold_uncertainty_summary.csv",
        index=False
    )

    imp_df.to_csv(OUTPUT_DIR / "rf_feature_importance.csv", index=False)
    print(overall_df.to_string(index=False))


if __name__ == "__main__":
    main()
