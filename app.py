import random
import pandas as pd
import streamlit as st
from utils import (
    get_card_kingdom_pricelist,
    get_dolar_blue_venta,
    load_faq,
    load_local_css,
    sidebar_file_loader,
    sidebar_file_saver,
)

# Always call set_page_config first
st.set_page_config(page_title="Automagic Calculator", layout="wide")


CANONICAL_COLS = ["Name", "API", "Edition", "Qtty", "CK", "CS", "MM", "Ago"]


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
    """Normalize blanks, NaN and zero-like values."""
    new_df = df.copy()

    for col in new_df.columns:
        new_df[col] = new_df[col].map(normalize_value)

    return new_df


def ensure_columns(df):
    """Guarantee the canonical columns exist, in order."""
    new_df = df.copy()

    for col in CANONICAL_COLS:
        if col not in new_df.columns:
            new_df[col] = None

    return new_df[CANONICAL_COLS]


def build_row_from_ck(card_name):
    """Look up a card's price/edition in ck_prices and build a single-row dict."""
    card_data = st.session_state.ck_prices.get(card_name, {})

    return {
        "Name": card_name,
        "API": normalize_value(card_data.get("price")),
        "Edition": normalize_value(card_data.get("edition")),
        "Qtty": 1,
    }


def update_base_editor():
    """Apply cell edits from the base grid smoothly without flashing."""
    editor_key = f"base_editor_{st.session_state.base_editor_key}"
    editor_state = st.session_state.get(editor_key, {"edited_rows": {}})

    df = st.session_state.data.copy()

    for row_idx, changes in editor_state.get("edited_rows", {}).items():
        row_idx = int(row_idx)

        for col, value in changes.items():
            if row_idx in df.index:
                df.at[row_idx, col] = value

    st.session_state.data = df


def update_qtty_editor():
    """Apply Qtty changes from the lower base grid to session state data."""
    editor_state = st.session_state.get("grid_base", {"edited_rows": {}})
    df = st.session_state.data.copy()

    for row_idx, changes in editor_state.get("edited_rows", {}).items():
        row_idx = int(row_idx)

        for col, value in changes.items():
            if row_idx in df.index and col == "Qtty":
                df.at[row_idx, col] = value

    st.session_state.data = df


def add_card_from_dropdown():
    """Immediately append a card picked from the dropdown and reset selection."""
    new_name = st.session_state.get("new_card_name", "")

    if not new_name:
        return

    new_row = pd.DataFrame([build_row_from_ck(new_name)])
    df = pd.concat(
        [st.session_state.data, new_row],
        ignore_index=True,
    )

    st.session_state.data = ensure_columns(df)

    # Force the upper editor to rebuild with the newly added row.
    st.session_state.base_editor_key += 1
    st.session_state.new_card_name = ""


def calculate_diego_tcg(name, qtty, price, added_margin, dolar_blue):
    if normalize_value(name) is None:
        return None

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


def calculate_mm(name, qtty, mm_price, dolar_blue):
    if normalize_value(name) is None:
        return None

    if pd.isna(qtty) or pd.isna(mm_price) or qtty is None or mm_price is None:
        return None

    if qtty == 0 or mm_price == 0:
        return None

    price = mm_price * dolar_blue * (1 + MM_MARGIN / 100)
    return int(round(qtty * (price + MM_FIXED_VALUE)))


def calculate_ago(name, qtty, ago_price, dolar_blue):
    if normalize_value(name) is None:
        return None

    if pd.isna(qtty) or pd.isna(ago_price) or qtty is None or ago_price is None:
        return None

    if qtty == 0 or ago_price == 0:
        return None

    return int(round(qtty * ago_price * dolar_blue))


def calculate_checked_totals(edited_df, qtty_series, col_name):
    """Sum both the price column and the Qtty for rows that are checked (✓)."""
    if "✓" not in edited_df.columns:
        return 0, 0

    mask = edited_df["✓"]

    price_total = (
        pd.to_numeric(edited_df.loc[mask, col_name], errors="coerce").fillna(0).sum()
    )

    qtty_total = pd.to_numeric(qtty_series.loc[mask], errors="coerce").fillna(0).sum()

    return price_total, qtty_total


def card_count(count):
    return f"{int(count)} card" if int(count) == 1 else f"{int(count)} cards"


# Load the external stylesheet
load_local_css("styles.css")


# Data initialization
CK_MARGIN = 20.0
CS_MARGIN = 13.0

dolar_blue = get_dolar_blue_venta()


if "ck_prices" not in st.session_state or not st.session_state.ck_prices:
    with st.spinner("Fetching Card Kingdom pricelist..."):
        st.session_state.ck_prices = get_card_kingdom_pricelist() or {}

        st.session_state.sorted_card_options = (
            sorted(st.session_state.ck_prices.keys())
            if st.session_state.ck_prices
            else []
        )


if "sorted_card_options" not in st.session_state:
    st.session_state.sorted_card_options = (
        sorted(st.session_state.ck_prices.keys()) if st.session_state.ck_prices else []
    )


if "data" not in st.session_state:
    if st.session_state.ck_prices:
        sample_names = random.sample(
            list(st.session_state.ck_prices.keys()),
            k=min(10, len(st.session_state.ck_prices)),
        )

        sample_names.sort(
            key=lambda name: st.session_state.ck_prices[name].get("price", 0),
            reverse=True,
        )

        seed_names = sample_names[:3]
        seed_rows = [build_row_from_ck(name) for name in seed_names]

        st.session_state.data = ensure_columns(pd.DataFrame(seed_rows))

    else:
        st.session_state.data = ensure_columns(pd.DataFrame())

else:
    st.session_state.data = ensure_columns(st.session_state.data)


if "base_editor_key" not in st.session_state:
    st.session_state.base_editor_key = 0


# Sidebar
st.sidebar.header("Variables")
st.sidebar.write("---")


MM_MARGIN = st.sidebar.number_input(
    "MM Margin (%)",
    min_value=0.0,
    value=5.0,
    step=1.0,
    format="%.1f",
)

MM_FIXED_VALUE = st.sidebar.number_input(
    "MM Fixed Value ($ ARS)",
    min_value=0,
    value=700,
    step=100,
)

st.sidebar.write("---")

agora_dolar_ref = st.sidebar.number_input(
    "Agora Dolar Reference ($ ARS)",
    min_value=0,
    value=int(dolar_blue),
    step=10,
)

st.sidebar.write("---")

st.sidebar.header("Data Management")

sidebar_file_loader()


st.session_state.data = ensure_columns(st.session_state.data)


@st.fragment
def main_content():
    st.title("Automagic Calculator")
    st.write("---")

    st.subheader("1. Enter Base Values")

    # Split into three independent widgets
    locked_df = st.session_state.data[["Name", "API", "Edition"]].copy()
    prices_df = st.session_state.data[["CK", "CS", "MM", "Ago"]].copy()

    locked_col, prices_col, delete_col = st.columns([3, 4, 0.5], gap="xsmall")

    with locked_col:
        # Read-only, so st.dataframe is enough — no editor state to manage
        # and no risk of it remounting when the prices grid is edited.
        st.dataframe(
            locked_df,
            width="stretch",
            height="content",
            hide_index=True,
            column_config={
                "Name": st.column_config.TextColumn(
                    "Card Name",
                    width="medium",
                ),
                "API": st.column_config.NumberColumn(
                    "🔒    Cheap Price",
                    format="%.2f",
                    step=0.01,
                    width="small",
                ),
                "Edition": st.column_config.TextColumn(
                    "🔒    Cheapest Edition",
                    width="medium",
                ),
            },
        )

    with prices_col:
        st.data_editor(
            prices_df,
            num_rows="fixed",
            width="stretch",
            height="content",
            hide_index=True,
            key=f"base_editor_{st.session_state.base_editor_key}",
            on_change=update_base_editor,
            column_config={
                "CK": st.column_config.NumberColumn(
                    "Card Kingdom",
                    format="%.2f",
                    step=0.01,
                ),
                "CS": st.column_config.NumberColumn(
                    "CoolStuffInc",
                    format="%.2f",
                    step=0.01,
                ),
                "MM": st.column_config.NumberColumn(
                    "Multi Margin",
                    format="%.2f",
                    step=0.01,
                ),
                "Ago": st.column_config.NumberColumn(
                    "Agora",
                    format="%.2f",
                    step=0.01,
                ),
            },
        )

    with delete_col:
        # st.dataframe (not data_editor) is enough here since ButtonColumn is
        # inherently read-only and there's no other editable state in this grid.
        delete_df = pd.DataFrame(
            {"Delete": [":material/delete:"] * len(st.session_state.data)}
        )

        st.dataframe(
            delete_df,
            height="content",
            hide_index=True,
            column_config={
                "Delete": st.column_config.ButtonColumn(
                    "Remove",
                    help="Delete row",
                    type="tertiary",
                    key="delete_btn_click",
                ),
            },
        )

    # Handle row deletion when a delete button is clicked.
    delete_click = st.session_state.get("delete_btn_click")

    if delete_click is not None:
        row_to_delete = (
            delete_click.get("row")
            if isinstance(delete_click, dict)
            else getattr(delete_click, "row", None)
        )

        if row_to_delete is not None and row_to_delete in st.session_state.data.index:
            st.session_state.data = st.session_state.data.drop(
                index=row_to_delete
            ).reset_index(drop=True)

            st.session_state.base_editor_key += 1
            st.rerun()

    # Card selector.
    st.selectbox(
        None,
        options=[
            "",
            *st.session_state.sorted_card_options,
        ],
        key="new_card_name",
        width=300,
        placeholder="Add card...",
        filter_mode="prefix",
        on_change=add_card_from_dropdown,
    )

    input_df = st.session_state.data
    sidebar_file_saver(input_df)
    st.sidebar.write("---")

    # Calculations
    calc_df = pd.DataFrame(index=input_df.index)

    calc_df["Name"] = input_df["Name"]
    calc_df["Qtty"] = input_df["Qtty"]

    calc_df["CK F"] = input_df.apply(
        lambda row: calculate_diego_tcg(
            row.get("Name", None),
            row.get("Qtty", None),
            row.get("CK", None),
            CK_MARGIN,
            dolar_blue,
        ),
        axis=1,
    )

    calc_df["CS F"] = input_df.apply(
        lambda row: calculate_diego_tcg(
            row.get("Name", None),
            row.get("Qtty", None),
            row.get("CS", None),
            CS_MARGIN,
            dolar_blue,
        ),
        axis=1,
    )

    calc_df["MM F"] = input_df.apply(
        lambda row: calculate_mm(
            row.get("Name", None),
            row.get("Qtty", None),
            row.get("MM", None),
            dolar_blue,
        ),
        axis=1,
    )

    calc_df["Ago F"] = input_df.apply(
        lambda row: calculate_ago(
            row.get("Name", None),
            row.get("Qtty", None),
            row.get("Ago", None),
            agora_dolar_ref,
        ),
        axis=1,
    )

    calc_df = normalize_df(calc_df)

    # Final Prices
    st.subheader("2. Final Prices")
    df_base = calc_df[["Name", "Qtty"]].copy()

    df_ck = pd.DataFrame(
        {
            "✓": False,
            "CK F": calc_df["CK F"],
        }
    )

    df_cs = pd.DataFrame(
        {
            "✓": False,
            "CS F": calc_df["CS F"],
        }
    )

    df_mm = pd.DataFrame(
        {
            "✓": False,
            "MM F": calc_df["MM F"],
        }
    )

    df_ago = pd.DataFrame(
        {
            "✓": False,
            "Ago F": calc_df["Ago F"],
        }
    )

    cols = st.columns([2, 1, 1, 1, 1], gap="xsmall")

    with cols[0]:
        st.data_editor(
            df_base,
            height="content",
            hide_index=True,
            key="grid_base",
            on_change=update_qtty_editor,
            disabled=["Name"],
            column_config={
                "Name": st.column_config.TextColumn(
                    "Card Name",
                    width="large",
                ),
                "Qtty": st.column_config.NumberColumn(
                    "Qtty",
                    format="%d",
                    step=1,
                    min_value=0,
                    width="small",
                ),
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
                "✓": st.column_config.CheckboxColumn(
                    "✓",
                    default=False,
                ),
                "CK F": st.column_config.NumberColumn(
                    "Card Kingdom",
                    format="$ %d",
                ),
            },
        )

        ck_subtotal, ck_count = calculate_checked_totals(
            edited_ck, calc_df["Qtty"], "CK F"
        )

        st.metric(
            "Subtotal",
            f"$ {int(ck_subtotal):,}",
        )
        st.write(card_count(ck_count))

    with cols[2]:
        edited_cs = st.data_editor(
            df_cs,
            width="stretch",
            height="content",
            hide_index=True,
            key="grid_cs",
            disabled=["CS F"],
            column_config={
                "✓": st.column_config.CheckboxColumn(
                    "✓",
                    default=False,
                ),
                "CS F": st.column_config.NumberColumn(
                    "CoolStuffInc",
                    format="$ %d",
                ),
            },
        )

        cs_subtotal, cs_count = calculate_checked_totals(
            edited_cs, calc_df["Qtty"], "CS F"
        )

        st.metric(
            "Subtotal",
            f"$ {int(cs_subtotal):,}",
        )
        st.write(card_count(cs_count))

    with cols[3]:
        edited_mm = st.data_editor(
            df_mm,
            width="stretch",
            height="content",
            hide_index=True,
            key="grid_mm",
            disabled=["MM F"],
            column_config={
                "✓": st.column_config.CheckboxColumn(
                    "✓",
                    default=False,
                ),
                "MM F": st.column_config.NumberColumn(
                    "Multi Margin",
                    format="$ %d",
                ),
            },
        )

        mm_subtotal, mm_count = calculate_checked_totals(
            edited_mm, calc_df["Qtty"], "MM F"
        )

        st.metric(
            "Subtotal",
            f"$ {int(mm_subtotal):,}",
        )
        st.write(card_count(mm_count))

    with cols[4]:
        edited_ago = st.data_editor(
            df_ago,
            width="stretch",
            height="content",
            hide_index=True,
            key="grid_ago",
            disabled=["Ago F"],
            column_config={
                "✓": st.column_config.CheckboxColumn(
                    "✓",
                    default=False,
                ),
                "Ago F": st.column_config.NumberColumn(
                    "Agora",
                    format="$ %d",
                ),
            },
        )

        ago_subtotal, ago_count = calculate_checked_totals(
            edited_ago, calc_df["Qtty"], "Ago F"
        )

        st.metric(
            "Subtotal",
            f"$ {int(ago_subtotal):,}",
        )
        st.write(card_count(ago_count))

    st.write(f"Dólar Blue: **$ {dolar_blue:.0f}**")
    st.write("---")

    with st.expander("❓ Frequently Asked Questions (F.A.Q.)"):
        st.markdown(load_faq("faq.md"))


main_content()
