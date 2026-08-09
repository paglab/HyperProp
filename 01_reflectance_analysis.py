"""
01_reflectance_analysis.py

Uses the SAME processed inputs as the original Analysis.py:
- data/wavelength_ref.npy
- data/reflectance/data_col_YYYYMMDD.npz

Each date .npz must contain ONLY the four keys already present in the project:
    ref, RTM, ELC, ELC3

No wavelengths need to be stored inside each .npz file.
"""

from pathlib import Path
import numpy as np
import pandas as pd

DATA_DIR = Path("data")
REFLECTANCE_DIR = DATA_DIR / "reflectance"
WAVELENGTH_FILE = DATA_DIR / "wavelength_ref.npy"
OUTPUT_DIR = Path("outputs/reflectance")

METHODS = ["RTM", "ELC", "ELC3"]

# Same filtering logic used in the project.
EXCLUDE_RANGES = [(400, 410), (940, 990), (1350, 1450)]


def band_mask(wavelengths):
    mask = np.ones(len(wavelengths), dtype=bool)
    for low, high in EXCLUDE_RANGES:
        mask &= ~((wavelengths >= low) & (wavelengths <= high))
    return mask


def sam_deg(reference, estimate):
    valid = np.isfinite(reference) & np.isfinite(estimate)
    r = reference[valid]
    e = estimate[valid]
    if r.size == 0:
        return np.nan
    denom = np.linalg.norm(r) * np.linalg.norm(e)
    if denom == 0:
        return np.nan
    cos_angle = np.clip(np.dot(r, e) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def rmse(reference, estimate):
    valid = np.isfinite(reference) & np.isfinite(estimate)
    if not np.any(valid):
        return np.nan
    return float(np.sqrt(np.mean((reference[valid] - estimate[valid]) ** 2)))


def analyze_date(npz_path, wavelengths):
    d = np.load(npz_path)
    required = {"ref", "RTM", "ELC", "ELC3"}
    missing = required.difference(d.files)
    if missing:
        raise KeyError(f"{npz_path.name} missing keys: {sorted(missing)}")

    mask = band_mask(wavelengths)
    ref = np.asarray(d["ref"], dtype=float)[:, mask]

    rows = []
    for method in METHODS:
        pred = np.asarray(d[method], dtype=float)[:, mask]
        if pred.shape != ref.shape:
            raise ValueError(
                f"{npz_path.name}: {method} {pred.shape} != ref {ref.shape}"
            )
        for plot_index in range(ref.shape[0]):
            rows.append({
                "Date": npz_path.stem.replace("data_col_", ""),
                "Plot_Index": plot_index + 1,
                "Method": method,
                "SAM_deg": sam_deg(ref[plot_index], pred[plot_index]),
                "RMSE": rmse(ref[plot_index], pred[plot_index]),
            })
    return rows


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    wavelengths = np.load(WAVELENGTH_FILE)
    input_files = sorted(REFLECTANCE_DIR.glob("data_col_*.npz"))
    if not input_files:
        raise FileNotFoundError(
            f"No data_col_*.npz files found in {REFLECTANCE_DIR.resolve()}"
        )

    rows = []
    for path in input_files:
        rows.extend(analyze_date(path, wavelengths))

    long_df = pd.DataFrame(rows)
    long_df.to_csv(OUTPUT_DIR / "spectral_metrics_by_plot.csv", index=False)

    summary = long_df.groupby(["Date", "Method"], as_index=False).agg(
        SAM_mean=("SAM_deg", "mean"),
        SAM_SD=("SAM_deg", "std"),
        RMSE_mean=("RMSE", "mean"),
        RMSE_SD=("RMSE", "std"),
    )
    summary.to_csv(OUTPUT_DIR / "spectral_metrics_summary.csv", index=False)

    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
