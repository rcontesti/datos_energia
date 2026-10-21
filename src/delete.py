
import pandas as pd

df = pd.read_parquet("data/processed/cgc_production_2026.parquet")

# Check whether a well appears more than once in a month.
keys = ["anio", "mes", "idpozo"]
duplicates = df[df.duplicated(keys, keep=False)].sort_values(keys)

print("Duplicate well-month rows:", len(duplicates))
print("Unique duplicated well-month keys:", duplicates[keys].drop_duplicates().shape[0])

if not duplicates.empty:
    cols = [
        "anio", "mes", "idpozo", "sigla", "empresa",
        "areapermisoconcesion", "prod_pet", "prod_gas",
    ]
    print(duplicates[cols].head(20).to_string(index=False))

# Compare direct CGC with the YPF partnership.
print("\nMonthly production by origin:")
print(
    df.groupby(["mes", "origen_grupo"])[["prod_pet", "prod_gas"]]
    .sum(min_count=1)
    .round(2)
    .to_string()
)
