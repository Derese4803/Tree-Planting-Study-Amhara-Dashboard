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
    FORM_XMLNS = st.secrets["commcare"].get("form_xmlns", "")
except KeyError as e:
    st.error(f"Missing configuration key in secrets: {e}")
    st.info(
        "Make sure `.streamlit/secrets.toml` or Streamlit Cloud Secrets has"
        " domain, username, and api_key configured."
    )
    st.stop()

# Target variables list requested
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
# 3. COMMCARE DAILY SAVED EXPORT FETCH FUNCTION (ROBUST)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)  # Caches fetched CSV in memory for 1 hour
def fetch_commcare_saved_export(domain, export_id, username, api_key, xmlns):
    """Fetches export data while verifying content type to avoid HTML tokenizer errors."""
    headers = {
        "Authorization": f"ApiKey {username}:{api_key}",
        "Accept": "text/csv, application/json",
    }

    # API endpoints targeting the saved export & form export endpoints
    urls = [
        f"https://www.commcarehq.org/a/{domain}/api/v0.5/form_export/{export_id}/?format=csv",
        f"https://www.commcarehq.org/a/{domain}/api/v0.5/form_export/?xmlns={xmlns}&format=csv" if xmlns else None,
        f"https://www.commcarehq.org/a/{domain}/reports/form/export/download/{export_id}/?format=csv",
    ]

    for url in urls:
        if not url:
            continue
        try:
            response = requests.get(url, headers=headers, timeout=90, allow_redirects=True)
            content_type = response.headers.get("Content-Type", "").lower()

            # Only attempt pandas parsing if response is 200 OK and NOT an HTML page
            if response.status_code == 200 and "html" not in content_type:
                # Check if the output actually looks like CSV data
                if response.text.startswith("<!DOCTYPE") or "<html" in response.text[:200].lower():
                    continue
                csv_data = io.StringIO(response.text)
                return pd.read_csv(csv_data, low_memory=False)
        except Exception:
            continue

    st.error(
        "Could not retrieve CSV data via API authentication. "
        "Verify your API Key and ensure the export feed is accessible."
    )
    return pd.DataFrame()


# -----------------------------------------------------------------------------
# 4. DASHBOARD INTERFACE
# -----------------------------------------------------------------------------
st.title("🌳 Tree Planting 2026 [South In-Person] — Main Survey")
st.caption(f"Domain: `{DOMAIN}` | Daily Saved Export ID: `{EXPORT_ID}`")

# Sidebar Controls
st.sidebar.header("Controls & Actions")
if st.sidebar.button("🔄 Force Refresh Export"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")

# Main Execution Flow
with st.spinner("Downloading CSV export from CommCare HQ..."):
    df_raw = fetch_commcare_saved_export(DOMAIN, EXPORT_ID, USERNAME, API_KEY, FORM_XMLNS)

if not df_raw.empty:
    # Match available target columns
    existing_target_cols = []
    for col in TARGET_COLUMNS:
        if col in df_raw.columns:
            existing_target_cols.append(col)
        elif f"form.{col}" in df_raw.columns:
            existing_target_cols.append(f"form.{col}")
        elif col.startswith("form.") and col[5:] in df_raw.columns:
            existing_target_cols.append(col[5:])

    # Filter dataset to available target columns
    df_display = df_raw[existing_target_cols] if existing_target_cols else df_raw

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
    st.warning("No data retrieved from the export feed. Click '🔄 Force Refresh Export' after checking secrets configuration.")
