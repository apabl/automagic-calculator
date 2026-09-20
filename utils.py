import os
import pandas as pd
import requests
import streamlit as st


def load_local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def load_faq(file_name="faq.md"):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            return f.read()
    return "F.A.Q. file not found. Please create an `faq.md` file in the application directory."


@st.cache_data(ttl=600)
def get_dolar_blue_venta():
    try:
        url = "https://dolarapi.com/v1/dolares/blue"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return float(response.json().get("venta", 1.0))
    except Exception:
        pass
    return 1.0


@st.cache_data(ttl=21600)  # 6 hours
def get_card_kingdom_pricelist():
    """Fetches and caches the Card Kingdom pricelist. Returns a dict of
    card name -> list of {price, edition, is_foil} dicts, one per printing,
    sorted non-foil-first then cheapest-first.
    """
    try:
        url = "https://api.cardkingdom.com/api/v2/pricelist"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json().get("data", [])
            ck_dict = {}

            for item in data:
                name = item.get("name", "").strip()

                if "token" in name.lower():
                    continue

                is_foil = item.get("is_foil", False)
                edition = item.get("edition", "").strip()

                try:
                    price = float(item.get("price_retail", 0.0))
                except (ValueError, TypeError):
                    price = 0.0

                if name and price > 0 and edition:
                    ck_dict.setdefault(name, []).append(
                        {"price": price, "edition": edition, "is_foil": is_foil}
                    )

            for printings in ck_dict.values():
                printings.sort(key=lambda p: (p["is_foil"], p["price"]))

            return ck_dict
    except Exception:
        pass
    return {}


def sidebar_file_loader():
    if "data_file_loaded" not in st.session_state:
        st.session_state.data_file_loaded = False

    if not st.session_state.data_file_loaded:
        uploaded_file = st.sidebar.file_uploader(None, type=["csv"])
        if uploaded_file is not None:
            try:
                loaded_df = pd.read_csv(uploaded_file)

                required_cols = ["Name", "Qtty", "CK", "CS", "MM", "Ago"]
                missing_cols = [
                    col for col in required_cols if col not in loaded_df.columns
                ]

                if missing_cols:
                    st.sidebar.error(
                        f"Incompatible file! Missing columns: {', '.join(missing_cols)}"
                    )
                    return

                # ck_prices now maps a card name to a LIST of printings
                # (sorted cheapest-first), not a single dict — take the
                # cheapest printing (index 0) to refresh API/Edition.
                ck_prices = st.session_state.get("ck_prices", {})
                api_values = []
                edition_values = []
                for name in loaded_df["Name"]:
                    printings = (
                        ck_prices.get(name, []) if isinstance(name, str) else []
                    )
                    cheapest = printings[0] if printings else {}
                    api_values.append(cheapest.get("price"))
                    edition_values.append(cheapest.get("edition"))

                loaded_df["API"] = api_values
                loaded_df["Edition"] = edition_values

                st.session_state.data = loaded_df
                st.session_state.data_file_loaded = True

                st.session_state.base_editor_key += 1
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error reading CSV file: {e}")
    else:
        st.sidebar.success("Data file loaded")

        if st.sidebar.button("Load Another File", use_container_width=True):
            st.session_state.data_file_loaded = False
            st.session_state.base_editor_key += 1
            st.rerun()


def sidebar_file_saver(current_df):
    try:
        csv_data = current_df.to_csv(index=False).encode("utf-8")
        st.sidebar.download_button(
            label="Save to .csv",
            data=csv_data,
            file_name="automagic_calculator.csv",
            mime="text/csv",
            icon=":material/download:",
            use_container_width=True,
        )
    except Exception as e:
        st.sidebar.error(f"Could not prepare save data: {e}")
