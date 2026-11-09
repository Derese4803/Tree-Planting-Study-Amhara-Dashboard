import streamlit as st
import requests
import pandas as pd

# -----------------------------------------------------------------------------
# 1. STREAMLIT PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Tree Planting Study [Amhara] — Dashboard",
    page_icon="🌳",
    layout="wide"
)

# -----------------------------------------------------------------------------
# 2. LOAD CREDENTIALS FROM STREAMLIT SECRETS
# -----------------------------------------------------------------------------
try:
    DOMAIN = st.secrets["commcare"]["domain"]
    USERNAME = st.secrets["commcare"]["username"]
    API_KEY = st.secrets["commcare"]["api_key"]
    FORM_XMLNS = st.secrets["commcare"]["form_xmlns"]
except KeyError as e:
    st.error(f"Missing configuration key in secrets: {e}")
    st.info("Make sure `.streamlit/secrets.toml` or Streamlit Cloud Secrets is configured properly.")
    st.stop()

# List of target columns requested for filtering
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
    "username"
]

# -----------------------------------------------------------------------------
# 3. COMMCARE API FETCH & FLATTENING FUNCTION (CACHED)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600)  # Automatically re-fetches from CommCare HQ every 1 hour
def load_commcare_data(domain, username, api_key, xmlns):
    """
    Queries CommCare HQ Form API v0.5 for the specified XMLNS,
    paginates through records, and flattens nested form survey variables.
    """
    base_url = f"https://www.commcarehq.org/a/{domain}/api/v0.5/form/"
    headers = {
        "Authorization": f"ApiKey {username}:{api_key}",
        "Accept": "application/json"
    }
    params = {
        "xmlns": xmlns,
        "limit": 100
    }
    
    all_records = []
    current_url = base_url
    max_pages = 20  # Up to 2,000 form submissions
    page_count = 0

    while current_url and page_count < max_pages:
        req_params = params if page_count == 0 else None
        
        try:
            response = requests.get(current_url, headers=headers, params=req_params, timeout=30)
            if response.status_code != 200:
                st.error(f"CommCare API Error (Status {response.status_code}): {response.text[:200]}")
                break
                
            data = response.json()
            objects = data.get("objects", [])
            
            for item in objects:
                record = {
                    "submission_id": item.get("id"),
                    "received_on": item.get("received_on"),
                    "user_id": item.get("user_id"),
                    "username": item.get("username")
                }
                
                # Unpack survey questionnaire variables ('form' object)
                form_body = item.get("form", {})
                if isinstance(form_body, dict):
                    _flatten_questions(form_body, "", record)
                    
                all_records.append(record)
                
            # Handle Pagination
            meta = data.get("meta", {})
            next_path = meta.get("next")
            if next_path:
                current_url = next_path if next_path.startswith("http") else f"https://www.commcarehq.org{next_path}"
            else:
                current_url = None
                
            page_count += 1

        except Exception as err:
            st.error(f"Failed to connect to CommCare HQ: {str(err)}")
            break

    return pd.DataFrame(all_records)


def _flatten_questions(obj, prefix, result):
    """Recursively flattens nested form groups into standard column names."""
    for key, value in obj.items():
        if key.startswith("@") or key.startswith("#"):
            continue
            
        col_name = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, dict):
            _flatten_questions(value, col_name, result)
        elif isinstance(value, list):
            result[col_name] = str(value)
        else:
            result[col_name] = value

# -----------------------------------------------------------------------------
# 4. DASHBOARD INTERFACE
# -----------------------------------------------------------------------------
st.title("🌳 Tree Planting Study [Amhara] — Filtered Dashboard")
st.caption(f"Domain: `{DOMAIN}` | Target Form XMLNS: `{FORM_XMLNS}`")

# Sidebar Controls
st.sidebar.header("Controls & Actions")
if st.sidebar.button("🔄 Force Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.info("Data auto-refreshes every hour. Click the button above to sync latest submissions immediately.")

# Main Body - Fetch & Render Data
with st.spinner("Connecting to CommCare HQ and fetching submissions..."):
    df_raw = load_commcare_data(DOMAIN, USERNAME, API_KEY, FORM_XMLNS)

if not df_raw.empty:
    # Filter DataFrame to include ONLY existing requested columns
    existing_target_cols = [col for col in TARGET_COLUMNS if col in df_raw.columns]
    
    # If some target columns have prefixes like 'form.', fallback matching handles both
    for col in TARGET_COLUMNS:
        alt_col = f"form.{col}"
        if col not in existing_target_cols and alt_col in df_raw.columns:
            existing_target_cols.append(alt_col)
            
    df_filtered = df_raw[existing_target_cols] if existing_target_cols else df_raw

    # ---------------------------------------------------------
    # TOP METRICS SUMMARY
    # ---------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Submissions", len(df_filtered))
    col2.metric("Target Fields Loaded", f"{len(existing_target_cols)} / {len(TARGET_COLUMNS)}")
    
    unique_users = df_raw["username"].nunique() if "username" in df_raw.columns else 0
    col3.metric("Active Enumerators", unique_users)

    st.markdown("---")

    # ---------------------------------------------------------
    # INTERACTIVE DATA EXPLORER & FILTERS
    # ---------------------------------------------------------
    st.subheader("Target Variables Explorer")
    
    selected_columns = st.multiselect(
        "Filter/Reorder target columns:",
        options=existing_target_cols,
        default=existing_target_cols
    )
    
    # Render Interactive Table
    st.dataframe(
        df_filtered[selected_columns] if selected_columns else df_filtered,
        use_container_width=True,
        height=450
    )

    # ---------------------------------------------------------
    # DOWNLOAD ACTION BUTTON
    # ---------------------------------------------------------
    csv_bytes = df_filtered.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Target Dataset (CSV)",
        data=csv_bytes,
        file_name="commcare_amhara_target_variables.csv",
        mime="text/csv"
    )

else:
    st.warning("No submission records were found for this form XMLNS on CommCare HQ.")
