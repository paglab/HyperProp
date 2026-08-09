"""
02_vi_mixed_effects.py

Uses the SAME VI files already used by the original Analysis.py.

Inputs:
- data/vi/0429/VIs.pkl
- data/vi/0531/VIs.pkl
- data/vi/0612/VIs.pkl
- data/vi/0625/VIs.pkl

Each VIs.pkl is the original dictionary.
For each VI, the array has shape (4, n_plots):
    row 0 = Reference
    row 1 = RTM
    row 2 = ELC
    row 3 = ELC3

No new VI CSV needs to be manually created.
"""

from pathlib import Path
import pickle
import warnings
import numpy as np
import pandas as pd
from scipy.stats import chi2
from statsmodels.formula.api import mixedlm

DATA_DIR = Path("data/vi")
OUTPUT_DIR = Path("outputs/vi")

PERIOD_FILES = {
    "0429": DATA_DIR / "0429" / "VIs.pkl",
    "0531": DATA_DIR / "0531" / "VIs.pkl",
    "0612": DATA_DIR / "0612" / "VIs.pkl",
    "0625": DATA_DIR / "0625" / "VIs.pkl",
}

VI_NAMES = ["NDVI", "NCNI", "NDWI_1640", "NRI850_1510", "LWVI2", "NDNI"]
METHOD_NAMES = ["Reference", "RTM", "ELC", "ELC3"]


def load_original_vi_files():
    all_data = {}
    for period, path in PERIOD_FILES.items():
        with open(path, "rb") as f:
            data = pickle.load(f)
        all_data[period] = {vi: np.asarray(data[vi]) for vi in VI_NAMES}
    return all_data


def prepare_long_data(all_data):
    rows = []
    for period, vi_dict in all_data.items():
        for vi, arr in vi_dict.items():
            if arr.shape[0] != 4:
                raise ValueError(
                    f"{period}-{vi}: expected first dimension 4, got {arr.shape}"
                )
            n_plots = arr.shape[1]
            for method_idx, method in enumerate(METHOD_NAMES):
                for sample_idx in range(n_plots):
                    rows.append({
                        "Period": period,
                        "VI": vi,
                        "Method": method,
                        "Plot_ID": sample_idx + 1,
                        # Same grouping rule used in the original analysis:
                        "Nitrogen_Level": "N1" if sample_idx < n_plots / 2 else "N3",
                        "Value": float(arr[method_idx, sample_idx]),
                    })
    return pd.DataFrame(rows)


def calculate_errors(long_df):
    ref = (
        long_df[long_df["Method"] == "Reference"]
        [["Period", "VI", "Plot_ID", "Value"]]
        .rename(columns={"Value": "Reference_Value"})
    )
    method_df = long_df[long_df["Method"] != "Reference"].copy()
    method_df = method_df.merge(
        ref,
        on=["Period", "VI", "Plot_ID"],
        how="left",
        validate="many_to_one"
    )
    method_df["Signed_Error"] = method_df["Value"] - method_df["Reference_Value"]
    method_df["Absolute_Error"] = method_df["Signed_Error"].abs()
    return method_df


def fit_model(formula, data):
    model = mixedlm(
        formula=formula,
        data=data,
        groups=data["Plot_ID"],
        re_formula="1"
    )
    last_error = None
    for optimizer in ["lbfgs", "powell", "cg"]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = model.fit(
                    reml=False,
                    method=optimizer,
                    maxiter=2000,
                    disp=False
                )
            if res.converged:
                return res
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"MixedLM failed: {formula}; {last_error}")


def lr_test(reduced, full):
    lr = max(0.0, 2.0 * (full.llf - reduced.llf))
    df = int(full.df_modelwc - reduced.df_modelwc)
    p = float(chi2.sf(lr, df))
    return lr, df, p


def format_p(p):
    if p < 0.001:
        return "<0.001***"
    if p < 0.01:
        return f"{p:.3f}**"
    if p < 0.05:
        return f"{p:.3f}*"
    return f"{p:.3f}"


def analyze_one_vi(sub):
    period_only = fit_model("Absolute_Error ~ C(Period)", sub)
    method_only = fit_model("Absolute_Error ~ C(Method)", sub)
    additive = fit_model("Absolute_Error ~ C(Method) + C(Period)", sub)
    full = fit_model("Absolute_Error ~ C(Method) * C(Period)", sub)

    method_test = lr_test(period_only, additive)
    period_test = lr_test(method_only, additive)
    interaction_test = lr_test(additive, full)

    plot_var = float(full.cov_re.iloc[0, 0])
    residual_var = float(full.scale)
    icc = (
        plot_var / (plot_var + residual_var)
        if (plot_var + residual_var) > 0 else np.nan
    )
    return full, method_test, period_test, interaction_test, icc


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_data = load_original_vi_files()
    long_df = prepare_long_data(all_data)
    error_df = calculate_errors(long_df)

    long_df.to_csv(OUTPUT_DIR / "vi_values_long.csv", index=False)
    error_df.to_csv(OUTPUT_DIR / "vi_absolute_errors_long.csv", index=False)

    table_rows = []
    for vi in VI_NAMES:
        sub = error_df[error_df["VI"] == vi].copy()
        full, m, t, inter, icc = analyze_one_vi(sub)

        with open(OUTPUT_DIR / f"mixed_model_{vi}.txt", "w", encoding="utf-8") as f:
            f.write(full.summary().as_text())

        table_rows.append({
            "VI": vi,
            "Method chi2 (df)": f"{m[0]:.2f} ({m[1]})",
            "Method p": format_p(m[2]),
            "Period chi2 (df)": f"{t[0]:.2f} ({t[1]})",
            "Period p": format_p(t[2]),
            "Method x Period chi2 (df)": f"{inter[0]:.2f} ({inter[1]})",
            "Method x Period p": format_p(inter[2]),
            "ICC": round(icc, 3),
        })

    table = pd.DataFrame(table_rows)
    table.to_csv(OUTPUT_DIR / "mixed_effects_tableVI.csv", index=False)
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
