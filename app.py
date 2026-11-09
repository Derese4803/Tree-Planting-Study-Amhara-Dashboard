import io
import pandas as pd
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. STREAMLIT PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tree Planting 2026 [South In-Person] — Main Survey",
    page_icon="🌳",
    layout="wide",
)

# -----------------------------------------------------------------------------
# 2. CONFIGURATION & TARGET VARIABLES
# -----------------------------------------------------------------------------
EXPORT_ID = "ec835f1ac45d12a69f16829a65e69007"

try:
    DOMAIN = st.secrets["commcare"]["domain"]
    USERNAME = st.secrets["commcare"]["username"]
    API_KEY = st.secrets["commcare"]["api_key"]
except KeyError as e:
    st.error(f"Missing configuration key in secrets: {e}")
    st.stop()

# Requested target variables
TARGET_COLUMNS = [
    "control_farmer.knows",
    "control_farmer.number",
    "form.control_farmer.name_1",
    "control_farmer.phonen_1",
    "form.control_farmer.name_2",
    "control_farmer.phonen_2",
    "control_farmer.name_3",
    "control_farmer.phonen_3",
    "control_farmer.name_4",
    "control_farmer.phonen_4",
    "control_farmer.name_5",
    "control_farmer.phonen_5",
    "region",
    "program",
    "woreda",
    "kebele",
    "treatment",
    "tno",
    "farmer_name",
    "phone_no",
    "unique_id",
    "username",
]


# -----------------------------------------------------------------------------
# 3. ROBUST COMMCARE FETCH FUNCTION (HANDLES CSV + EXCEL)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)
def fetch_commcare_saved_export(domain, export_id, username, api_key):
    """Downloads CommCare Daily Saved Export handling both CSV and Excel formats."""

    # Candidate URLs with explicit CSV format flags
    candidate_urls = [
        f"https://www.commcarehq.org/a/{domain}/data/export/custom/dailysaved/download/{export_id}/?format=csv",
        f"https://www.commcarehq.org/a/{domain}/data/export/custom/dailysaved/download/{export_id}/",
    ]

    # Try both Basic Auth and ApiKey header
    auth_options = [
        ("basic", (username, api_key), None),
        ("header", None, {"Authorization": f"ApiKey {username}:{api_key}"}),
    ]

    for url in candidate_urls:
        for auth_label, auth_tuple, header_dict in auth_options:
            try:
                if auth_label == "basic":
                    res = requests.get(
                        url, auth=auth_tuple, timeout=90, allow_redirects=True
                    )
                else:
                    res = requests.get(
                        url,
                        headers=header_dict,
                        timeout=90,
                        allow_redirects=True,
                    )

                if res.status_code != 200:
                    continue

                content_type = res.headers.get("Content-Type", "").lower()

                # Ignore HTML Login redirects
                if (
                    "text/html" in content_type
                    or res.text.strip().startswith("<!DOCTYPE")
                ):
                    continue

                # 1. Try parsing as CSV
                try:
                    df = pd.read_csv(io.StringIO(res.text), low_memory=False)
                    if not df.empty:
                        return df
                except Exception:
                    pass

                # 2. Try parsing as Excel binary stream (.xlsx / .xls)
                try:
                    df = pd.read_excel(io.BytesIO(res.content))
                    if not df.empty:
                        return df
                except Exception:
                    pass

            except Exception:
                continue

    return pd.DataFrame()


# -----------------------------------------------------------------------------
# 4. DASHBOARD INTERFACE
# -----------------------------------------------------------------------------
st.title("🌳 Tree Planting 2026 [South In-Person] — Main Survey")
st.caption(f"Domain: `{DOMAIN}` | Daily Saved Export ID: `{EXPORT_ID}`")

# Sidebar Controls
st.sidebar.header("Controls & Actions")
if st.sidebar.button("🔄 Force Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")

# Main Execution Flow
with st.spinner("Downloading 2.1 MB dataset from CommCare HQ..."):
    df_raw = fetch_commcare_saved_export(DOMAIN, EXPORT_ID, USERNAME, API_KEY)

if not df_raw.empty:
    st.success("✅ Dataset successfully loaded!")

    # Flexible matching for target variables
    existing_target_cols = []
    for col in TARGET_COLUMNS:
        if col in df_raw.columns:
            existing_target_cols.append(col)
        elif f"form.{col}" in df_raw.columns:
            existing_target_cols.append(f"form.{col}")
        elif col.startswith("form.") and col[5:] in df_raw.columns:
            existing_target_cols.append(col[5:])

    df_display = (
        df_raw[existing_target_cols] if existing_target_cols else df_raw
    )

    # ---------------------------------------------------------
    # SUMMARY METRICS
    # ---------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Submissions", len(df_raw))
    col2.metric("Total Export Columns", len(df_raw.columns))
    col3.metric(
        "Target Fields Matched",
        f"{len(existing_target_cols)} / {len(TARGET_COLUMNS)}",
    )

    st.markdown("---")

    # ---------------------------------------------------------
    # DATA EXPLORER & FILTERS
    # ---------------------------------------------------------
    st.subheader("Target Variables Explorer")

    available_cols = df_display.columns.tolist()
    selected_cols = st.multiselect(
        "Select/Filter columns to show:",
        options=available_cols,
        default=available_cols,
    )

    st.dataframe(
        df_display[selected_cols] if selected_cols else df_display,
        use_container_width=True,
        height=450,
    )

    # ---------------------------------------------------------
    # DOWNLOAD ACTION BUTTON
    # ---------------------------------------------------------
    csv_bytes = df_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Target Variables CSV",
        data=csv_bytes,
        file_name="tree_planting_2026_south_in_person_target.csv",
        mime="text/csv",
    )

else:
    st.error("Failed to parse the downloaded file.")
