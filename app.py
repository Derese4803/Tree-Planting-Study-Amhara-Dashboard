import io
import pandas as pd
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 1. STREAMLIT PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tree Planting 2026 [South In-Person] — Feed Diagnostics",
    page_icon="🌳",
    layout="wide",
)

# -----------------------------------------------------------------------------
# 2. LOAD SECRETS
# -----------------------------------------------------------------------------
EXPORT_ID = "ec835f1ac45d12a69f16829a65e69007"

try:
    DOMAIN = st.secrets["commcare"]["domain"]
    USERNAME = st.secrets["commcare"]["username"]
    API_KEY = st.secrets["commcare"]["api_key"]
    FORM_XMLNS = st.secrets["commcare"].get("form_xmlns", "")
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

st.title("🌳 CommCare Feed Diagnostic & Dashboard")
st.caption(f"Domain: `{DOMAIN}` | Target Export ID: `{EXPORT_ID}`")

if st.sidebar.button("🔄 Clear Cache & Retry Connections"):
    st.cache_data.clear()
    st.rerun()


# -----------------------------------------------------------------------------
# 3. DIAGNOSTIC FETCH EXECUTION
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300)
def diagnose_commcare_connection(domain, export_id, username, api_key, xmlns):
    results = []
    successful_df = pd.DataFrame()

    # Define test strategies
    attempts = [
        {
            "name": "1. Daily Saved Feed (Basic Auth)",
            "url": f"https://www.commcarehq.org/a/{domain}/data/export/custom/dailysaved/download/{export_id}/",
            "auth_type": "basic",
        },
        {
            "name": "2. Daily Saved Feed (ApiKey Header)",
            "url": f"https://www.commcarehq.org/a/{domain}/data/export/custom/dailysaved/download/{export_id}/",
            "auth_type": "header",
        },
        {
            "name": "3. Form Export API v0.5 (by Export ID)",
            "url": f"https://www.commcarehq.org/a/{domain}/api/v0.5/form_export/{export_id}/?format=csv",
            "auth_type": "header",
        },
        {
            "name": "4. Form Export API v0.5 (by Form XMLNS)",
            "url": f"https://www.commcarehq.org/a/{domain}/api/v0.5/form_export/?xmlns={xmlns}&format=csv"
            if xmlns
            else None,
            "auth_type": "header",
        },
    ]

    for attempt in attempts:
        if not attempt["url"]:
            continue

        log_entry = {"name": attempt["name"], "url": attempt["url"]}

        try:
            if attempt["auth_type"] == "basic":
                # Basic Auth pass
                res = requests.get(
                    attempt["url"],
                    auth=(username, api_key),
                    timeout=45,
                    allow_redirects=True,
                )
            else:
                # ApiKey Header pass
                headers = {"Authorization": f"ApiKey {username}:{api_key}"}
                res = requests.get(
                    attempt["url"],
                    headers=headers,
                    timeout=45,
                    allow_redirects=True,
                )

            log_entry["status_code"] = res.status_code
            log_entry["content_type"] = res.headers.get("Content-Type", "")
            log_entry["final_url"] = res.url

            # Content verification
            is_html = (
                "text/html" in log_entry["content_type"]
                or res.text.strip().startswith("<!DOCTYPE")
                or "<html" in res.text[:200].lower()
            )

            if res.status_code == 200 and not is_html:
                log_entry["success"] = True
                log_entry["snippet"] = "CSV Data Stream Received Successfully!"
                if successful_df.empty:
                    successful_df = pd.read_csv(
                        io.StringIO(res.text), low_memory=False
                    )
            else:
                log_entry["success"] = False
                log_entry["snippet"] = (
                    res.text[:250].replace("\n", " ") + "..."
                )

        except Exception as err:
            log_entry["success"] = False
            log_entry["status_code"] = "Error"
            log_entry["snippet"] = str(err)

        results.append(log_entry)

    return successful_df, results


with st.spinner("Testing CommCare endpoints..."):
    df_raw, logs = diagnose_commcare_connection(
        DOMAIN, EXPORT_ID, USERNAME, API_KEY, FORM_XMLNS
    )

# -----------------------------------------------------------------------------
# 4. DISPLAY RESULTS OR DETAILED DIAGNOSTICS
# -----------------------------------------------------------------------------
if not df_raw.empty:
    st.success("✅ Successfully established connection and fetched CSV dataset!")

    # Match target variables against columns in dataset
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

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Submissions", len(df_raw))
    col2.metric("Total Export Columns", len(df_raw.columns))
    col3.metric(
        "Target Fields Matched",
        f"{len(existing_target_cols)} / {len(TARGET_COLUMNS)}",
    )

    st.subheader("Target Variables Explorer")
    st.dataframe(df_display, use_container_width=True, height=400)

    csv_bytes = df_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download Target Variables CSV",
        data=csv_bytes,
        file_name="tree_planting_2026_south_in_person_target.csv",
        mime="text/csv",
    )

else:
    st.error("❌ All connection attempts failed to retrieve a raw CSV stream.")
    st.subheader("🔍 Endpoint Diagnostic Log")

    for log in logs:
        with st.expander(
            f"{'✅' if log.get('success') else '❌'} {log['name']} (Status:"
            f" {log.get('status_code')})"
        ):
            st.write(f"**Target URL:** `{log['url']}`")
            st.write(f"**Final Redirect URL:** `{log.get('final_url')}`")
            st.write(f"**Content-Type:** `{log.get('content_type')}`")
            st.write("**Response Snippet:**")
            st.code(log.get("snippet"), language="html")
