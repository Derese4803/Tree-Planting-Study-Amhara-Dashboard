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
# 3. COMMCARE FETCH FUNCTION WITH DUAL AUTH (CACHED)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_commcare_saved_export(
    domain, export_id, username, api_key, xmlns=""
):
    """Tries Basic Auth for Daily Saved Export web routes and ApiKey header for API routes."""
    debug_logs = []

    # Strategy A: Daily Saved Export web routes using Basic Authentication
    web_urls = [
        f"https://www.commcarehq.org/a/{domain}/data/export/custom/dailysaved/download/{export_id}/",
        f"https://www.commcarehq.org/a/{domain}/reports/form/export/download/{export_id}/?format=csv",
    ]

    for url in web_urls:
        try:
            # Using HTTP Basic Auth for web endpoints
            response = requests.get(
                url, auth=(username, api_key), timeout=90, allow_redirects=True
            )
            content_type = response.headers.get("Content-Type", "").lower()

            if (
                response.status_code == 200
                and "html" not in content_type
                and not response.text.strip().startswith("<!DOCTYPE")
            ):
                csv_data = io.StringIO(response.text)
                df = pd.read_csv(csv_data, low_memory=False)
                return df, debug_logs
            else:
                debug_logs.append(
                    f"Basic Auth Route failed ({response.status_code}): {url}"
                )
        except Exception as err:
            debug_logs.append(f"Basic Auth Exception: {str(err)}")

    # Strategy B: CommCare API Token Authentication (ApiKey header)
    api_headers = {"Authorization": f"ApiKey {username}:{api_key}"}
    api_urls = [
        f"https://www.commcarehq.org/a/{domain}/api/v0.5/form_export/{export_id}/?format=csv",
        f"https://www.commcarehq.org/a/{domain}/api/v0.5/form_export/?xmlns={xmlns}&format=csv"
        if xmlns
        else None,
    ]

    for url in api_urls:
        if not url:
            continue
        try:
            response = requests.get(
                url,
                headers=api_headers,
                timeout=90,
                allow_redirects=True,
            )
            content_type = response.headers.get("Content-Type", "").lower()

            if (
                response.status_code == 200
                and "html" not in content_type
                and not response.text.strip().startswith("<!DOCTYPE")
            ):
                csv_data = io.StringIO(response.text)
                df = pd.read_csv(csv_data, low_memory=False)
                return df, debug_logs
            else:
                debug_logs.append(
                    f"API Route failed ({response.status_code}): {url}"
                )
        except Exception as err:
            debug_logs.append(f"API Route Exception: {str(err)}")

    return pd.DataFrame(), debug_logs


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
with st.spinner("Connecting to CommCare HQ export feed..."):
    df_raw, debug_logs = fetch_commcare_saved_export(
        DOMAIN, EXPORT_ID, USERNAME, API_KEY, FORM_XMLNS
    )

# Debug Expander in Sidebar
with st.sidebar.expander("🔍 Diagnostics & Logs", expanded=df_raw.empty):
    for log in debug_logs:
        st.write(log)

if not df_raw.empty:
    # Match target variables against columns in dataset
    existing_target_cols = []
    for col in TARGET_COLUMNS:
        if col in df_raw.columns:
            existing_target_cols.append(col)
        elif f"form.{col}" in df_raw.columns:
            existing_target_cols.append(f"form.{col}")
        elif col.startswith("form.") and col[5:] in df_raw.columns:
            existing_target_cols.append(col[5:])

    # Filter dataset to matched columns
    df_display = (
        df_raw[existing_target_cols] if existing_target_cols else df_raw
    )

    # Summary Metrics
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Submissions", len(df_raw))
    col2.metric("Total Export Columns", len(df_raw.columns))
    col3.metric(
        "Target Fields Matched",
        f"{len(existing_target_cols)} / {len(TARGET_COLUMNS)}",
    )

    st.markdown("---")

    # Data Display
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

    # Download Button
    csv_bytes = df_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Target Variables CSV",
        data=csv_bytes,
        file_name="tree_planting_2026_south_in_person_target.csv",
        mime="text/csv",
    )

else:
    st.error("Unable to retrieve CSV file from CommCare feed.")
    st.info(
        "**Troubleshooting Checklist:**\n"
        "1. Open CommCare HQ -> **Data** -> **Daily Saved Exports**.\n"
        "
