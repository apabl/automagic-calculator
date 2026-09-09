import streamlit as st
import pandas as pd
import requests

# Always call set_page_config first
st.set_page_config(page_title="Grid Calculator", layout="wide")

# Fixed Constants
CK_MARGIN = 20.0
CS_MARGIN = 13.0

# Sidebar - Configurable Constants
st.sidebar.header("MM Calculation Settings")

MM_MARGIN = st.sidebar.number_input(
    "MM Margin (%)", min_value=0.0, value=5.0, step=1.0, format="%.1f"
)
MM_FIXED_VALUE = st.sidebar.number_input(
    "MM Fixed Value ($ ARS)", min_value=0, value=700, step=100
)

st.sidebar.write("---")
st.sidebar.write(f"Streamlit v{st.__version__}")

@st.cache_data(ttl=600)
def get_dolar_blue_venta():
    """ Fetchs Dólar Blue (Venta) rate """
    try:
        url = "https://dolarapi.com/v1/dolares/blue"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return float(response.json().get("venta", 1.0))
    except Exception:
        pass
    return 1.0

def calculate_diego_tcg(qtty, price, added_margin, dolar_blue):
    if pd.isna(qtty) or pd.isna(price) or qtty == 0 or price == 0:
        return 0
    
    if price < 1:
        fee = 0.5
    elif price < 20:
        fee = 1.0
    else:
        fee = qtty * price * 0.05
        
    base = (price * qtty) + fee
    return int(round(base * (1 + added_margin / 100) * dolar_blue))

def calculate_mm(qtty, mm_price, dolar_blue):
    if pd.isna(qtty) or pd.isna(mm_price) or qtty == 0 or mm_price == 0:
        return 0
    return int(round(qtty * (mm_price * dolar_blue * (1 + MM_MARGIN / 100) + MM_FIXED_VALUE)))

def calculate_ago(qtty, ago_price, dolar_blue):
    if pd.isna(qtty) or pd.isna(ago_price) or qtty == 0 or ago_price == 0:
        return 0
    return int(round(qtty * ago_price * dolar_blue))

st.title("Interactive Grid Calculator")

dolar_blue = get_dolar_blue_venta()
st.caption(f"Dólar Blue: **$ {dolar_blue:.0f}**")

st.write("---")

# Starting dataset
INITIAL_DATA = pd.DataFrame(
    [
        {"Name": "Item C", "Qtty": 1, "CK": 8.99, "CS": 9.99, "MM": 10.99, "Ago": 1.00},
        {"Name": "Item A", "Qtty": 4, "CK": 7.99, "CS": 8.49, "MM": 8.49, "Ago": 1.99},
        {"Name": "Item B", "Qtty": 1, "CK": 0.99, "CS": 0.99, "MM": 1.29, "Ago": 1.00},
    ]
)

# 1. Base Input Grid
st.subheader("1. Enter Base Values")
input_df = st.data_editor(
    INITIAL_DATA,
    num_rows="dynamic",
    width="stretch",
    key="data_editor",
    column_config={
        "CK": st.column_config.NumberColumn("CK", format="%.2f", step=0.01),
        "CS": st.column_config.NumberColumn("CS", format="%.2f", step=0.01),
        "MM": st.column_config.NumberColumn("MM", format="%.2f", step=0.01),
        "Ago": st.column_config.NumberColumn("Ago", format="%.2f", step=0.01),
    }
)

# 2. Process Calculations & Prepare Checkbox Grid
calc_df = pd.DataFrame()
calc_df["Name"] = input_df["Name"]
calc_df["Qtty"] = input_df["Qtty"].fillna(0).astype(int)

calc_df["CK F"] = input_df.apply(
    lambda row: calculate_diego_tcg(row.get("Qtty", 0), row.get("CK", 0), CK_MARGIN, dolar_blue), axis=1
)
calc_df["CS F"] = input_df.apply(
    lambda row: calculate_diego_tcg(row.get("Qtty", 0), row.get("CS", 0), CS_MARGIN, dolar_blue), axis=1
)
calc_df["MM F"] = input_df.apply(
    lambda row: calculate_mm(row.get("Qtty", 0), row.get("MM", 0), dolar_blue), axis=1
)
calc_df["Ago F"] = input_df.apply(
    lambda row: calculate_ago(row.get("Qtty", 0), row.get("Ago", 0), dolar_blue), axis=1
)

# Construct Dataframe with interspersed Checkbox columns
grid_df = pd.DataFrame({
    "Name": calc_df["Name"],
    "Qtty": calc_df["Qtty"],
    "✓ CK": False,
    "CK F": calc_df["CK F"],
    "✓ CS": False,
    "CS F": calc_df["CS F"],
    "✓ MM": False,
    "MM F": calc_df["MM F"],
    "✓ Ago": False,
    "Ago F": calc_df["Ago F"],
})

# 3. Output Grid with Interactive Checkboxes
st.subheader("2. Final Prices (Check cells to sum column totals)")

edited_grid = st.data_editor(
    grid_df,
    width="stretch",
    hide_index=True,
    key="output_grid",
    disabled=["Name", "Qtty", "CK F", "CS F", "MM F", "Ago F"],  # Only allow checkbox toggles
    column_config={
        "Qtty": st.column_config.NumberColumn("Qtty", format="%d"),
        "✓ CK": st.column_config.CheckboxColumn("Sel", default=False),
        "CK F": st.column_config.NumberColumn("CK F", format="$ %d"),
        "✓ CS": st.column_config.CheckboxColumn("Sel", default=False),
        "CS F": st.column_config.NumberColumn("CS F", format="$ %d"),
        "✓ MM": st.column_config.CheckboxColumn("Sel", default=False),
        "MM F": st.column_config.NumberColumn("MM F", format="$ %d"),
        "✓ Ago": st.column_config.CheckboxColumn("Sel", default=False),
        "Ago F": st.column_config.NumberColumn("Ago F", format="$ %d"),
    }
)

# Calculate dynamic sums for checked cells
ck_sum = edited_grid.loc[edited_grid["✓ CK"], "CK F"].sum()
cs_sum = edited_grid.loc[edited_grid["✓ CS"], "CS F"].sum()
mm_sum = edited_grid.loc[edited_grid["✓ MM"], "MM F"].sum()
ago_sum = edited_grid.loc[edited_grid["✓ Ago"], "Ago F"].sum()

# Quantity sum for any row where at least one provider is checked
any_checked = (
    edited_grid["✓ CK"] | edited_grid["✓ CS"] | edited_grid["✓ MM"] | edited_grid["✓ Ago"]
)
qtty_sum = edited_grid.loc[any_checked, "Qtty"].sum()

total_checked_count = edited_grid[["✓ CK", "✓ CS", "✓ MM", "✓ Ago"]].sum().sum()

# Display dynamic summary table
if total_checked_count > 0:
    summary_title = f"Checked Cells Total ({total_checked_count} item(s) selected)"
else:
    summary_title = "Checked Cells Total (Check items above to calculate sum)"

totals_df = pd.DataFrame([{
    "Name": "TOTAL",
    "Qtty": int(qtty_sum),
    "CK F": int(ck_sum),
    "CS F": int(cs_sum),
    "MM F": int(mm_sum),
    "Ago F": int(ago_sum),
}])

st.markdown(f"### {summary_title}")
st.dataframe(
    totals_df,
    width="stretch",
    hide_index=True,
    column_config={
        "Name": st.column_config.TextColumn(""),
        "Qtty": st.column_config.NumberColumn("Selected Qtty", format="%d"),
        "CK F": st.column_config.NumberColumn("Total CK", format="$ %d"),
        "CS F": st.column_config.NumberColumn("Total CS", format="$ %d"),
        "MM F": st.column_config.NumberColumn("Total MM", format="$ %d"),
        "Ago F": st.column_config.NumberColumn("Total Ago", format="$ %d"),
    }
)