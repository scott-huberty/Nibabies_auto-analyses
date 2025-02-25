from pathlib import Path

import pandas as pd



GENDER_DICT = {
    "sub-1019": "Male",
    "sub-1375": "Female",
    }

BABIES_WANT_COLS = ["study_id",
                    "neonatal_status_v2",
                    "sixmo_status_v2",
                    "neonatal_notscan_v2",
                    "sixmo_notscan_v2",
                    "infant_sex",
                    "child_sex",
                    ]

PANDAS_DTYPES = {"study_id": "string",
                "neonatal_status_v2": "object",
                "sixmo_status_v2": "object",
                "neonatal_notscan_v2": "object",
                "sixmo_notscan_v2": "object",
                "infant_sex": "object",
                "child_sex": "object",
                }
assert len(BABIES_WANT_COLS) == len(PANDAS_DTYPES)


def get_redcap_df(fname, fname_datadict, project="BABIES"):
    """The main API for reading the REDcap data."""
    df_datadict = read_datadict(fname_datadict)
    df_redcap = process_redcap_df(read_redcap(fname, project), df_datadict, project)
    return df_redcap


def read_datadict(fname_datadict):
    return pd.read_csv(fname_datadict, index_col="Variable / Field Name")


def read_redcap(fname, project="BABIES"):
    if project == "BABIES":
        usecols = BABIES_WANT_COLS
        index_col = "study_id"
    dtypes = _get_csv_dtypes(project)
    assert len(usecols) == len(dtypes)
    # columns have mixed types and we cant really force them to be a single type
    return pd.read_csv(
        fname,
        usecols=usecols,
        na_values=pd.NA,
        dtype=dtypes,
        index_col=index_col,
        )


def process_redcap_df(df_redcap, df_datadict, project="BABIES"):
    if project == "BABIES":
        # Drop study ID's that are not 1000-1999
        ids_to_drop = ~df_redcap.reset_index()["study_id"].astype(str).str.match(r"1\d{3}")
    else:
        raise NotImplementedError("Project must be 'BABIES'")
    df_redcap.drop(df_redcap.index[ids_to_drop], inplace=True)
    # df_redcap.set_index("study_id", inplace=True)    # Prepend "sub-" to study ID's
    df_redcap.index = "sub-" + df_redcap.index

    if project == "BABIES":
        need_cols = BABIES_WANT_COLS.copy()
        need_cols.pop(need_cols.index("study_id"))
    for column in need_cols:
        df_redcap = _map_codes(df_redcap, df_datadict, column)
    df_redcap = get_biological_sex(df_redcap, project)
    df_redcap = drop_non_enrolled(df_redcap)
    return df_redcap


def drop_non_enrolled(df):
    return df.dropna(subset=["neonatal_status_v2", "sixmo_status_v2"], how="all")

def _get_csv_dtypes(project="BABIES"):
    if project == "BABIES":
        return PANDAS_DTYPES
    raise ValueError(f"Project {project} not recognized.")


def _map_codes(df_redcap, df_datadict, column):
    missing_dict = _get_code_dict(df_datadict, column)
    df_redcap[column] = df_redcap[column].replace(missing_dict)
    return df_redcap

def _get_code_dict(df_datadict, column):
    missing_dict = {}
    missingness_string = df_datadict.loc[column, "Choices, Calculations, OR Slider Labels"]
    missingness = missingness_string.split("|")
    for segment in missingness:
        key, value = segment.split(", ", 1)
        missing_dict[key.strip()] = value.strip()
    return missing_dict


def get_biological_sex(df, project="BABIES"):
    # 1. check if infant_sex is missing
    # 2. if missing, check if child_sex is missing
    # 3. if still missing, check GENDER_DICT variable for hard coded value
    # 4. if 1, 2, & 3 are missing, return "Missing"
    # 5. if either is not missing, return the value
    # 6. if both are not missing, assert that they are the same
    # 7. if they are the same, return the value
    # 8. if they are different, raise an error
    df["Biological Sex"] = "Missing"
    for ii, row in df.iterrows():
        # First Babies
        if project == "BABIES":
            if isinstance(row["infant_sex"], str) and isinstance(row["child_sex"], str):
                if row["infant_sex"] == row["child_sex"]:
                    df.at[ii, "Biological Sex"] = row["infant_sex"]
                else:
                    raise ValueError(f"Row {ii} has different values for infant and child sex.\n"
                                    f"({row['infant_sex']} and {row['child_sex']})")
            if _is_falsey(row["infant_sex"]):
                if _is_falsey(row["child_sex"]):
                    biological_sex = GENDER_DICT.get(row.name, None)
                    if not biological_sex:
                        continue
                    else:
                        df.at[ii, "Biological Sex"] = biological_sex
                else:
                    df.at[ii, "Biological Sex"] = row["child_sex"]
            else:
                df.at[ii, "Biological Sex"] = row["infant_sex"]
    drop_cols = ["infant_sex", "child_sex", "babys_sex"]
    for col in drop_cols:
        if col in df.columns:
            df.drop(col, axis=1, inplace=True)
    return df


def _is_falsey(val):
    if val is None:
        return True
    elif isinstance(val, str) and val.lower() in ["", "na", "nan", "none", "n/a"]:
        return True
    elif not val:
        return True
    elif pd.isna(val):
        return True
    return False