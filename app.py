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

# 2. Process Calculations
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

# Prepare dataframes for side-by-side grids
df_ck = pd.DataFrame({"✓": False, "CK F": calc_df["CK F"]})
df_cs = pd.DataFrame({"✓": False, "CS F": calc_df["CS F"]})
df_mm = pd.DataFrame({"✓": False, "MM F": calc_df["MM F"]})
df_ago = pd.DataFrame({"✓": False, "Ago F": calc_df["Ago F"]})

# 3. Output Grids Side-by-Side with Column Metrics
st.subheader("2. Final Prices")

cols = st.columns(4)

# with cols[0]:
#     st.markdown("**Details**")
#     edited_base = st.data_editor(
#         df_base,
#         width="stretch",
#         hide_index=True,
#         key="grid_base",
#         disabled=["Name", "Qtty"],
#         column_config={
#             "Name": st.column_config.TextColumn("Name", width="medium"),
#             "Qtty": st.column_config.NumberColumn("Qtty", format="%d", width="small"),
#         }
#     )
    
#     # Calculate Selected Qtty using session state of all checkboxes safely
#     ck_s = st.session_state.get("grid_ck", df_ck)
#     cs_s = st.session_state.get("grid_cs", df_cs)
#     mm_s = st.session_state.get("grid_mm", df_mm)
#     ago_s = st.session_state.get("grid_ago", df_ago)
    
#     chk_ck = ck_s["✓"] if isinstance(ck_s, pd.DataFrame) and "✓" in ck_s.columns else pd.Series([False]*len(df_base))
#     chk_cs = cs_s["✓"] if isinstance(cs_s, pd.DataFrame) and "✓" in cs_s.columns else pd.Series([False]*len(df_base))
#     chk_mm = mm_s["✓"] if isinstance(mm_s, pd.DataFrame) and "✓" in mm_s.columns else pd.Series([False]*len(df_base))
#     chk_ago = ago_s["✓"] if isinstance(ago_s, pd.DataFrame) and "✓" in ago_s.columns else pd.Series([False]*len(df_base))
    
#     any_checked = chk_ck | chk_cs | chk_mm | chk_ago
#     qtty_sum = edited_base.loc[any_checked, "Qtty"].sum() if len(edited_base) == len(any_checked) else 0
    
#     st.metric("Selected Qtty", int(qtty_sum))

with cols[0]:
    edited_ck = st.data_editor(
        df_ck,
        width="stretch",
        hide_index=True,
        key="grid_ck",
        disabled=["CK F"],
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False, width="small"),
            "CK F": st.column_config.NumberColumn("CK F", format="$ %d", width="medium"),
        }
    )
    ck_sum = edited_ck.loc[edited_ck["✓"], "CK F"].sum() if "✓" in edited_ck.columns else 0
    st.metric("Total CK", f"$ {int(ck_sum):,}")

with cols[1]:
    edited_cs = st.data_editor(
        df_cs,
        width="stretch",
        hide_index=True,
        key="grid_cs",
        disabled=["CS F"],
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False, width="small"),
            "CS F": st.column_config.NumberColumn("CS F", format="$ %d", width="medium"),
        }
    )
    cs_sum = edited_cs.loc[edited_cs["✓"], "CS F"].sum() if "✓" in edited_cs.columns else 0
    st.metric("Total CS", f"$ {int(cs_sum):,}")

with cols[2]:
    edited_mm = st.data_editor(
        df_mm,
        width="stretch",
        hide_index=True,
        key="grid_mm",
        disabled=["MM F"],
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False, width="small"),
            "MM F": st.column_config.NumberColumn("MM F", format="$ %d", width="medium"),
        }
    )
    mm_sum = edited_mm.loc[edited_mm["✓"], "MM F"].sum() if "✓" in edited_mm.columns else 0
    st.metric("Total MM", f"$ {int(mm_sum):,}")

with cols[3]:
    edited_ago = st.data_editor(
        df_ago,
        width="stretch",
        hide_index=True,
        key="grid_ago",
        disabled=["Ago F"],
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False, width="small"),
            "Ago F": st.column_config.NumberColumn("Ago F", format="$ %d", width="medium"),
        }
    )
    ago_sum = edited_ago.loc[edited_ago["✓"], "Ago F"].sum() if "✓" in edited_ago.columns else 0
    st.metric("Total Ago", f"$ {int(ago_sum):,}")
