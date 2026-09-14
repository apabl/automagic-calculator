import os
import pandas as pd
import requests
import streamlit as st


def load_local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def load_faq(file_name="faq.md"):
    """Loads the F.A.Q. content from a markdown file."""
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
    """Fetches and caches the Card Kingdom pricelist, finding the cheapest
    non-foil (or fallback foil) price, expansion name, and full SKU
    across all versions/printings.
    """
    try:
        url = "https://api.cardkingdom.com/api/v2/pricelist"
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json().get("data", [])
            non_foil_data = {}
            foil_data = {}

            for item in data:
                name = item.get("name", "").strip().lower()
                is_foil = item.get("is_foil", False)
                edition = item.get("edition", "").strip()
                sku = item.get("sku", "").strip()

                try:
                    price = float(item.get("price_retail", 0.0))
                except (ValueError, TypeError):
                    price = 0.0

                if name and price > 0:
                    card_info = {
                        "price": price,
                        "edition": edition,
                        "sku": sku
                    }

                    if not is_foil:
                        if name not in non_foil_data or price < non_foil_data[name]["price"]:
                            non_foil_data[name] = card_info
                    else:
                        if name not in foil_data or price < foil_data[name]["price"]:
                            foil_data[name] = card_info

            # Combine: Prefer the lowest non-foil price,
            # fallback to lowest foil if no non-foil exists
            ck_dict = {}
            all_names = set(non_foil_data.keys()).union(set(foil_data.keys()))
            for name in all_names:
                if name in non_foil_data:
                    ck_dict[name] = non_foil_data[name]
                else:
                    ck_dict[name] = foil_data[name]

            return ck_dict
    except Exception:
        pass
    return {}


def set_default_data():
    return pd.DataFrame(
        [
            {
                "Name": "Counterspell",
                "Qtty": 1,
                "API": 0.00,
                "CK": 0.00,
                "CS": 0.00,
                "MM": 0.00,
                "Ago": 0.00,
            },
            {
                "Name": "Dark Ritual",
                "Qtty": 1,
                "API": 0.00,
                "CK": 0.00,
                "CS": 0.00,
                "MM": 0.00,
                "Ago": 0.00,
            },
            {
                "Name": "Disenchant",
                "Qtty": 4,
                "API": 0.00,
                "CK": 0.00,
                "CS": 0.00,
                "MM": 0.00,
                "Ago": 0.00,
            },
        ]
    )


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

                st.session_state.data = loaded_df
                st.session_state.data_file_loaded = True
                if "base_editor" in st.session_state:
                    del st.session_state["base_editor"]
                st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error reading CSV file: {e}")
    else:
        st.sidebar.success("Data file loaded")

        if st.sidebar.button("Load Another File", use_container_width=True):
            st.session_state.data_file_loaded = False
            if "base_editor" in st.session_state:
                del st.session_state["base_editor"]
            st.rerun()


def sidebar_file_saver(current_df):
    try:
        csv_data = current_df.to_csv(index=False).encode("utf-8")
        st.sidebar.download_button(
            label="Save to .csv",
            data=csv_data,
            file_name="automagic_calculator.csv",
            mime="text/csv",
            use_container_width=True,
        )
    except Exception as e:
        st.sidebar.error(f"Could not prepare save data: {e}")
