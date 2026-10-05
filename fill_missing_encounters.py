import pandas as pd
from pathlib import Path

base = Path(r"C:\Users\sathy\OneDrive\Documents\Desktop\Jeeva\data_cleaning\analytics")

obs_file = base / "analytics_observations.csv"
enc_file = base / "analytics_encounters.csv"
output_file = base / "analytics_observations_structured.csv"

print("Loading observations...")
observations = pd.read_csv(obs_file, low_memory=False)

print("Loading encounters...")
encounters = pd.read_csv(enc_file, low_memory=False)

print("\n=== BEFORE ===")
print("Observation rows:", len(observations))
print("Missing ENCOUNTER:", observations["ENCOUNTER"].isna().sum())

# Convert dates
observations["DATE_DT"] = pd.to_datetime(
    observations["DATE"], errors="coerce"
)

encounters["START_DT"] = pd.to_datetime(
    encounters["START"], errors="coerce"
)

encounters["STOP_DT"] = pd.to_datetime(
    encounters["STOP"], errors="coerce"
)

# Only observations with missing encounter
missing_mask = observations["ENCOUNTER"].isna()

# Group encounters by patient for fast lookup
encounter_groups = {
    patient: group
    for patient, group in encounters.groupby("PATIENT", sort=False)
}

filled = 0
no_match = 0

print("\nFilling missing ENCOUNTER values...")

for idx in observations.index[missing_mask]:

    patient = observations.at[idx, "PATIENT"]
    obs_date = observations.at[idx, "DATE_DT"]

    if patient not in encounter_groups:
        no_match += 1
        continue

    candidates = encounter_groups[patient].copy()

    if pd.isna(obs_date):
        # If observation date is unavailable, use the first encounter
        selected = candidates.iloc[0]
    else:
        # Prefer encounters whose date range contains the observation date
        inside = candidates[
            (candidates["START_DT"] <= obs_date)
            & (
                candidates["STOP_DT"].isna()
                | (candidates["STOP_DT"] >= obs_date)
            )
        ]

        if not inside.empty:
            # If multiple encounters contain the date,
            # choose the one with the closest START date.
            inside = inside.copy()
            inside["distance"] = (
                inside["START_DT"] - obs_date
            ).abs()

            selected = inside.sort_values("distance").iloc[0]

        else:
            # No encounter range contains the date.
            # Choose the encounter with the closest START date.
            candidates = candidates.copy()
            candidates["distance"] = (
                candidates["START_DT"] - obs_date
            ).abs()

            candidates = candidates.dropna(subset=["distance"])

            if candidates.empty:
                no_match += 1
                continue

            selected = candidates.sort_values("distance").iloc[0]

    observations.at[idx, "ENCOUNTER"] = selected["ID"]
    filled += 1

# Remove helper column
observations.drop(columns=["DATE_DT"], inplace=True)

print("\n=== RESULT ===")
print("Rows:", len(observations))
print("Previously missing:", missing_mask.sum())
print("Successfully filled:", filled)
print("Could not fill:", no_match)
print("Remaining NULL:", observations["ENCOUNTER"].isna().sum())

observations.to_csv(output_file, index=False)

print("\nSaved:")
print(output_file)
