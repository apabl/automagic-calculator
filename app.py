import random
import pandas as pd
import streamlit as st
from streamlit_searchbox import st_searchbox
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


CANONICAL_COLS = ["Name", "Edition", "Qtty", "CK", "CS", "MM", "Ago"]


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


def format_edition_name(printing):
    """Format edition name, prefixing with 'Foil - ' if it's a foil printing."""
    if not printing:
        return None

    edition = printing.get("edition", "Unknown")
    is_foil = printing.get("foil") or printing.get("is_foil") or False

    if isinstance(is_foil, str):
        is_foil = is_foil.lower() in ["true", "1", "yes", "foil"]

    prefix = "Foil - " if is_foil else ""
    return f"{prefix}{edition}"


def build_row_from_ck(card_name, printing=None):
    """Look up a card's price/edition in ck_prices and build a single-row dict.
    ck_prices now maps a card name to a list of printings (sorted cheapest first).
    """
    printings = st.session_state.ck_prices.get(card_name, [])

    if printing is None:
        printing = printings[0] if printings else {}

    return {
        "Name": card_name,
        "CK": normalize_value(printing.get("price")),
        "Edition": normalize_value(format_edition_name(printing)),
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


def add_card(card_name, printing=None):
    """Append a card selected from the searchbox with a chosen printing."""
    if not card_name:
        return

    new_row = pd.DataFrame([build_row_from_ck(card_name, printing=printing)])
    df = pd.concat(
        [st.session_state.data, new_row],
        ignore_index=True,
    )

    st.session_state.data = ensure_columns(df)

    # Force the upper editor to rebuild with the newly added row.
    st.session_state.base_editor_key += 1


def handle_edition_selection():
    """Callback triggered instantly when an edition is chosen from the dropdown."""
    selected_label = st.session_state.get("edition_picker_selectbox")
    pending_card = st.session_state.get("pending_card")

    if (
        pending_card
        and selected_label
        and selected_label != "--- Select an edition ---"
    ):
        printings = st.session_state.ck_prices.get(pending_card, [])
        printing_options = {
            f"{format_edition_name(p)} — ${p.get('price', 0):.2f}": p for p in printings
        }
        chosen_printing = printing_options.get(selected_label)
        add_card(pending_card, chosen_printing)

    # Clear all states completely so the dropdown disappears and search resets
    st.session_state.pending_card = None
    st.session_state._last_selected_card = None
    st.session_state.pop("card_searchbox", None)
    st.session_state.pop("edition_picker_selectbox", None)


def search_cards(query: str):
    """Server-side filter for the searchbox — only the matched subset (capped
    at 50) is ever sent to the browser."""
    if len(query) < 2:
        return []

    query_lower = query.lower()

    return [
        name
        for name in st.session_state.sorted_card_options
        if query_lower in name.lower()
    ][:50]


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

# Always kept in sync with ck_prices — recomputed unconditionally rather than
# guarded by "not in session_state", so it can never go stale if ck_prices
# is ever refreshed by another path.
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
            key=lambda name: (
                st.session_state.ck_prices[name][0]["price"]
                if st.session_state.ck_prices[name]
                else 0
            ),
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

    # Split into two independent widgets
    locked_df = st.session_state.data[["Name", "Edition"]].copy()
    prices_df = st.session_state.data[["CK", "CS", "MM", "Ago"]].copy()

    locked_col, prices_col = st.columns([2.5, 4], gap="xsmall")

    with locked_col:
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

    # Card selector — server-side filtered searchbox
    search_col, _ = st.columns([1, 4])

    with search_col:
        selected_card = st_searchbox(
            search_cards,
            key="card_searchbox",
            placeholder="Add card...",
            clear_on_submit=True,
            rerun_scope="fragment",
        )

    # Trigger edition selection flow when a new card is selected from the searchbox
    if selected_card and selected_card != st.session_state.get("_last_selected_card"):
        st.session_state._last_selected_card = selected_card
        st.session_state.pending_card = selected_card
        st.rerun(scope="fragment")

    # Edition Selection UI Prompt when a card has been picked from search
    pending_card = st.session_state.get("pending_card")
    if pending_card:
        printings = st.session_state.ck_prices.get(pending_card, [])

        if printings:
            st.markdown(f"**Choose edition for `{pending_card}`:**")
            printing_options = {
                f"{format_edition_name(p)} — ${p.get('price', 0):.2f}": p
                for p in printings
            }

            options_list = ["--- Select an edition ---"] + list(printing_options.keys())

            st.selectbox(
                "Select Edition",
                options=options_list,
                key="edition_picker_selectbox",
                on_change=handle_edition_selection,
                label_visibility="collapsed",
            )
        else:
            # If no printings exist, add it automatically without edition
            add_card(pending_card, None)
            st.session_state.pending_card = None
            st.session_state._last_selected_card = None
            st.rerun(scope="fragment")

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

    cols = st.columns([0.5, 2, 1, 1, 1, 1], gap="xsmall")

    with cols[0]:
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

    with cols[1]:
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

    with cols[2]:
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

    with cols[3]:
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

    with cols[4]:
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

    with cols[5]:
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
