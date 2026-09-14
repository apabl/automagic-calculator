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


def normalize_value(value):
    """Convert empty/zero-like values to None."""
    if pd.isna(value):
        return None

    if isinstance(value, str):
        value = value.strip()
        return value if value else None

    if isinstance(value, (int, float)) and value == 0:
        return None

    return value


def normalize_df(df):
    """Normalize blanks, NaN and zero-like values across the dataframe."""
    new_df = df.copy()

    for col in new_df.columns:
        new_df[col] = new_df[col].map(normalize_value)

    return new_df


def sync_api_prices(df):
    """Aligns API prices and editions with current card names and enforces proper column order."""
    updated = False
    new_df = normalize_df(df)

    if "Name" not in new_df.columns:
        return new_df, False

    # Define the canonical column order: Name, Edition, API, Qtty, CS, CK, MM, Ago
    canonical_cols = ["Name", "Edition", "API", "Qtty", "CS", "CK", "MM", "Ago"]

    # Ensure all canonical columns exist
    for col in canonical_cols:
        if col not in new_df.columns:
            new_df[col] = None
            updated = True

    # Enforce strict column sequencing
    existing_canonical = [col for col in canonical_cols if col in new_df.columns]
    other_cols = [col for col in new_df.columns if col not in canonical_cols]
    ordered_cols = existing_canonical + other_cols

    if list(new_df.columns) != ordered_cols:
        new_df = new_df[ordered_cols]
        updated = True

    for idx, row in new_df.iterrows():
        card_name = normalize_value(row.get("Name"))

        # Name is the key. No name means no API-derived data.
        if card_name is None:
            if new_df.at[idx, "Edition"] is not None:
                new_df.at[idx, "Edition"] = None
                updated = True

            if new_df.at[idx, "API"] is not None:
                new_df.at[idx, "API"] = None
                updated = True

            continue

        card_data = st.session_state.ck_prices.get(card_name.lower(), {})

        expected_api = normalize_value(card_data.get("price"))
        expected_edition = normalize_value(card_data.get("edition"))

        if new_df.at[idx, "API"] != expected_api:
            new_df.at[idx, "API"] = expected_api
            updated = True

        if new_df.at[idx, "Edition"] != expected_edition:
            new_df.at[idx, "Edition"] = expected_edition
            updated = True

    return new_df, updated


def update_base_editor():
    """Apply data editor changes and synchronize API-derived fields."""
    # Construct the correct dynamic key matching the data editor widget
    editor_key = f"base_editor_{st.session_state.base_editor_key}"

    # Safely retrieve the editor state, defaulting to an empty structure if missing
    editor_state = st.session_state.get(
        editor_key, {"edited_rows": {}, "deleted_rows": [], "added_rows": []}
    )

    df = st.session_state.data.copy()

    # Apply edited cells
    for row_idx, changes in editor_state.get("edited_rows", {}).items():
        row_idx = int(row_idx)

        for col, value in changes.items():
            if row_idx in df.index:
                df.at[row_idx, col] = value

    # Delete rows
    deleted_rows = editor_state.get("deleted_rows", [])

    if deleted_rows:
        df = df.drop(index=deleted_rows)

    # Add rows
    added_rows = editor_state.get("added_rows", [])

    if added_rows:
        df = pd.concat(
            [df, pd.DataFrame(added_rows)],
            ignore_index=True,
        )

    df = df.reset_index(drop=True)
    df, _ = sync_api_prices(df)

    st.session_state.data = df

    # Changing the editor key forces only this editor to use the
    # synchronized dataframe on the next fragment rerun.
    st.session_state.base_editor_key += 1


def calculate_diego_tcg(qtty, price, added_margin, dolar_blue):
    if pd.isna(qtty) or pd.isna(price) or qtty is None or price is None:
        return None

    if qtty == 0 or price == 0:
        return None

    if price < 1:
        fee = 0.5
    elif price < 20:
        fee = 1.0
    else:
        fee = qtty * price * 0.05

    base = (price * qtty) + fee
    return int(round(base * (1 + added_margin / 100) * dolar_blue))


def calculate_mm(qtty, mm_price, dolar_blue):
    if pd.isna(qtty) or pd.isna(mm_price) or qtty is None or mm_price is None:
        return None

    if qtty == 0 or mm_price == 0:
        return None

    return int(
        round(qtty * (mm_price * dolar_blue * (1 + MM_MARGIN / 100) + MM_FIXED_VALUE))
    )


def calculate_ago(qtty, ago_price, dolar_blue):
    if pd.isna(qtty) or pd.isna(ago_price) or qtty is None or ago_price is None:
        return None

    if qtty == 0 or ago_price == 0:
        return None

    return int(round(qtty * ago_price * dolar_blue))


# Load the external stylesheet
load_local_css("styles.css")

# Data initialization
CK_MARGIN = 20.0
CS_MARGIN = 13.0

dolar_blue = get_dolar_blue_venta()

if "ck_prices" not in st.session_state or not st.session_state.ck_prices:
    with st.spinner("Fetching Card Kingdom pricelist..."):
        st.session_state.ck_prices = get_card_kingdom_pricelist() or {}

if "data" not in st.session_state:
    st.session_state.data = normalize_df(set_default_data())
else:
    st.session_state.data = normalize_df(st.session_state.data)

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

# Covers app startup & file loading
st.session_state.data, _ = sync_api_prices(st.session_state.data)


@st.fragment
def main_content():
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
        on_change=update_base_editor,
        disabled=["Edition", "API"],
        column_config={
            "Name": st.column_config.TextColumn("Card Name", width="medium"),
            "Edition": st.column_config.TextColumn(
                "🔒    Cheapest Edition", width="medium"
            ),
            "API": st.column_config.NumberColumn(
                "🔒    Cheapest Price", format="%.2f", step=0.01, width="small"
            ),
            "Qtty": st.column_config.NumberColumn(
                "Qtty", format="%d", step=1, min_value=0, width="small"
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

    # Use the synchronized dataframe
    input_df = st.session_state.data

    # File saver uses the synchronized DataFrame
    sidebar_file_saver(input_df)
    st.sidebar.write("---")

    # 2. Process Calculations using synchronized input
    calc_df = pd.DataFrame()
    calc_df["Name"] = input_df["Name"]
    calc_df["Qtty"] = input_df["Qtty"]

    calc_df["CK F"] = input_df.apply(
        lambda row: calculate_diego_tcg(
            row.get("Qtty", None), row.get("CK", None), CK_MARGIN, dolar_blue
        ),
        axis=1,
    )

    calc_df["CS F"] = input_df.apply(
        lambda row: calculate_diego_tcg(
            row.get("Qtty", None), row.get("CS", None), CS_MARGIN, dolar_blue
        ),
        axis=1,
    )

    calc_df["MM F"] = input_df.apply(
        lambda row: calculate_mm(
            row.get("Qtty", None), row.get("MM", None), dolar_blue
        ),
        axis=1,
    )

    calc_df["Ago F"] = input_df.apply(
        lambda row: calculate_ago(
            row.get("Qtty", None), row.get("Ago", None), agora_dolar_ref
        ),
        axis=1,
    )

    calc_df = normalize_df(calc_df)

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
            pd.to_numeric(edited_ck.loc[edited_ck["✓"], "CK F"], errors="coerce")
            .fillna(0)
            .sum()
            if "✓" in edited_ck.columns
            else 0
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
            pd.to_numeric(edited_cs.loc[edited_cs["✓"], "CS F"], errors="coerce")
            .fillna(0)
            .sum()
            if "✓" in edited_cs.columns
            else 0
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
            pd.to_numeric(edited_mm.loc[edited_mm["✓"], "MM F"], errors="coerce")
            .fillna(0)
            .sum()
            if "✓" in edited_mm.columns
            else 0
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
            pd.to_numeric(edited_ago.loc[edited_ago["✓"], "Ago F"], errors="coerce")
            .fillna(0)
            .sum()
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


main_content()
