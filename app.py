import pandas as pd
import streamlit as st
from utils import (
    get_card_kingdom_pricelist,
    get_dolar_blue_venta,
    load_faq,
    load_local_css,
    set_default_data,
    sidebar_file_loader,
    sidebar_file_saver,
)

# Always call set_page_config first
st.set_page_config(page_title="Automagic Calculator", layout="wide")


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
    return int(
        round(qtty * (mm_price * dolar_blue * (1 + MM_MARGIN / 100) + MM_FIXED_VALUE))
    )


def calculate_ago(qtty, ago_price, dolar_blue):
    if pd.isna(qtty) or pd.isna(ago_price) or qtty == 0 or ago_price == 0:
        return 0
    return int(round(qtty * ago_price * dolar_blue))


# Load the external stylesheet
load_local_css("styles.css")

# Data initialization variables
CK_MARGIN = 20.0
CS_MARGIN = 13.0
dolar_blue = get_dolar_blue_venta()

if "data" not in st.session_state:
    st.session_state.data = set_default_data()

if "base_editor_key" not in st.session_state:
    st.session_state.base_editor_key = 0


# Sidebar
st.sidebar.header("Variables")
st.sidebar.write("---")

MM_MARGIN = st.sidebar.number_input(
    "MM Margin (%)", min_value=0.0, value=5.0, step=1.0, format="%.1f"
)
MM_FIXED_VALUE = st.sidebar.number_input(
    "MM Fixed Value ($ ARS)", min_value=0, value=700, step=100
)
st.sidebar.write("---")

agora_dolar_ref = st.sidebar.number_input(
    "Agora Dolar Reference ($ ARS)", min_value=0, value=int(dolar_blue), step=10
)
st.sidebar.write("---")

st.sidebar.header("Data Management")

sidebar_file_loader()


# Main Page
st.title("Automagic Calculator")
st.write("---")

# 1. Base Input Grid
st.subheader("1. Enter Base Values")

input_df = st.data_editor(
    st.session_state.data,
    num_rows="dynamic",
    width="stretch",
    height="content",
    key=f"base_editor_{st.session_state.base_editor_key}",
    disabled=["API"],
    column_config={
        "Name": st.column_config.TextColumn("Card Name", width="medium"),
        "Qtty": st.column_config.NumberColumn(
            "Qtty", format="%d", step=1, min_value=0, width="small"
        ),
        "API": st.column_config.NumberColumn(
            "🔒    Cheapest CK NM", format="%.2f", step=0.01, width="small"
        ),
        "CS": st.column_config.NumberColumn(
            "CoolStuffInc", format="%.2f", step=0.01, width="small"
        ),
        "CK": st.column_config.NumberColumn(
            "Card Kingdom", format="%.2f", step=0.01, width="small"
        ),
        "MM": st.column_config.NumberColumn(
            "Multi Margin", format="%.2f", step=0.01, width="small"
        ),
        "Ago": st.column_config.NumberColumn(
            "Agora", format="%.2f", step=0.01, width="small"
        ),
    },
)

# API update button
if st.button("Update CK Prices", use_container_width=False):
    with st.spinner("Fetching Card Kingdom pricelist..."):
        current_df = input_df.copy()
        ck_prices = get_card_kingdom_pricelist()

        if ck_prices:
            updated_count = 0
            not_found_count = 0

            for idx, row in current_df.iterrows():
                card_name = str(row.get("Name", "")).strip().lower()

                if card_name in ck_prices:
                    current_df.at[idx, "API"] = ck_prices[card_name]
                    updated_count += 1
                else:
                    not_found_count += 1

            # Replace the backing dataset only because the API has actually
            # changed the underlying data, then recreate the editor once.
            st.session_state.data = current_df
            st.session_state.base_editor_key += 1

            st.success(
                f"Updated API prices for {updated_count} card(s). "
                f"{not_found_count} card(s) not found (left unchanged)."
            )
            st.rerun()
        else:
            st.error("Failed to fetch Card Kingdom price list.")

# File saver uses the live edited DataFrame directly
sidebar_file_saver(input_df)
st.sidebar.write("---")


# 2. Process Calculations using input_df directly
calc_df = pd.DataFrame()
calc_df["Name"] = input_df["Name"]
calc_df["Qtty"] = input_df["Qtty"].fillna(0).astype(int)

calc_df["CK F"] = input_df.apply(
    lambda row: calculate_diego_tcg(
        row.get("Qtty", 0), row.get("CK", 0), CK_MARGIN, dolar_blue
    ),
    axis=1,
)
calc_df["CS F"] = input_df.apply(
    lambda row: calculate_diego_tcg(
        row.get("Qtty", 0), row.get("CS", 0), CS_MARGIN, dolar_blue
    ),
    axis=1,
)
calc_df["MM F"] = input_df.apply(
    lambda row: calculate_mm(row.get("Qtty", 0), row.get("MM", 0), dolar_blue),
    axis=1,
)
calc_df["Ago F"] = input_df.apply(
    lambda row: calculate_ago(row.get("Qtty", 0), row.get("Ago", 0), agora_dolar_ref),
    axis=1,
)

# 3. Output Grids with Column Metrics
st.subheader("2. Final Prices")

df_base = calc_df[["Name", "Qtty"]].copy()
df_ck = pd.DataFrame({"✓": False, "CK F": calc_df["CK F"]})
df_cs = pd.DataFrame({"✓": False, "CS F": calc_df["CS F"]})
df_mm = pd.DataFrame({"✓": False, "MM F": calc_df["MM F"]})
df_ago = pd.DataFrame({"✓": False, "Ago F": calc_df["Ago F"]})

cols = st.columns([1.2, 1, 1, 1, 1])

with cols[0]:
    edited_base = st.data_editor(
        df_base,
        width="stretch",
        height="content",
        hide_index=True,
        key="grid_base",
        disabled=["Name", "Qtty"],
        column_config={
            "Name": st.column_config.TextColumn("Card Name", width="medium"),
            "Qtty": st.column_config.NumberColumn("Qtty", format="%d"),
        },
    )

with cols[1]:
    edited_ck = st.data_editor(
        df_ck,
        width="stretch",
        height="content",
        hide_index=True,
        key="grid_ck",
        disabled=["CK F"],
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False),
            "CK F": st.column_config.NumberColumn(
                "Card Kingdom", format="$ %d", width="medium"
            ),
        },
    )
    ck_sum = (
        edited_ck.loc[edited_ck["✓"], "CK F"].sum() if "✓" in edited_ck.columns else 0
    )
    st.metric("Subtotal", f"$ {int(ck_sum):,}")

with cols[2]:
    edited_cs = st.data_editor(
        df_cs,
        width="stretch",
        height="content",
        hide_index=True,
        key="grid_cs",
        disabled=["CS F"],
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False),
            "CS F": st.column_config.NumberColumn(
                "CoolStuffInc", format="$ %d", width="medium"
            ),
        },
    )
    cs_sum = (
        edited_cs.loc[edited_cs["✓"], "CS F"].sum() if "✓" in edited_cs.columns else 0
    )
    st.metric("Subtotal", f"$ {int(cs_sum):,}")

with cols[3]:
    edited_mm = st.data_editor(
        df_mm,
        width="stretch",
        height="content",
        hide_index=True,
        key="grid_mm",
        disabled=["MM F"],
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False),
            "MM F": st.column_config.NumberColumn(
                "Multi Margin", format="$ %d", width="medium"
            ),
        },
    )
    mm_sum = (
        edited_mm.loc[edited_mm["✓"], "MM F"].sum() if "✓" in edited_mm.columns else 0
    )
    st.metric("Subtotal", f"$ {int(mm_sum):,}")

with cols[4]:
    edited_ago = st.data_editor(
        df_ago,
        width="stretch",
        height="content",
        hide_index=True,
        key="grid_ago",
        disabled=["Ago F"],
        column_config={
            "✓": st.column_config.CheckboxColumn("✓", default=False),
            "Ago F": st.column_config.NumberColumn(
                "Agora", format="$ %d", width="medium"
            ),
        },
    )
    ago_sum = (
        edited_ago.loc[edited_ago["✓"], "Ago F"].sum()
        if "✓" in edited_ago.columns
        else 0
    )
    st.metric("Subtotal", f"$ {int(ago_sum):,}")

st.caption(f"Dólar Blue: **$ {dolar_blue:.0f}**")

# F.A.Q. SECTION
st.write("---")
with st.expander("❓ Frequently Asked Questions (F.A.Q.)"):
    faq_text = load_faq("faq.md")
    st.markdown(faq_text)
