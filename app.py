import streamlit as st
import pandas as pd
from simple_salesforce import Salesforce

st.set_page_config(page_title="Ruthless Report Liberator", page_icon="🧨", layout="wide")

st.title("🧨 The Ruthless Report Liberator")
st.markdown("Find the dashboards holding your reports hostage, neutralize the dependencies, and purge your org.")

# --- SIDEBAR: AUTHENTICATION ---
with st.sidebar:
    st.header("Authentication")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    security_token = st.text_input("Security Token", type="password")
    domain = st.selectbox("Domain", ["login", "test"])
    
    if st.button("Connect", type="primary"):
        try:
            st.session_state['sf'] = Salesforce(
                username=username, password=password, 
                security_token=security_token, domain=domain
            )
            st.success("Successfully connected to Salesforce.")
        except Exception as e:
            st.error(f"Connection failed: {e}")

# --- MAIN APP: DEPENDENCY HUNTER ---
if 'sf' in st.session_state:
    sf = st.session_state['sf']
    base_url = sf.sf_instance
    
    st.markdown("---")
    st.subheader("Target Acquisition")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("🔍 Enter exact Report ID (00O...) or partial Report Name:")
    with col2:
        st.write("")
        st.write("")
        execute_hunt = st.button("Hunt Dependencies", type="primary", use_container_width=True)

    if execute_hunt and search_term:
        with st.spinner("Scanning for targets..."):
            # 1. Fetch the Reports
            is_id = search_term.startswith('00O') and len(search_term) in [15, 18]
            
            if is_id:
                report_query = f"SELECT Id, Name, DeveloperName FROM Report WHERE Id = '{search_term}'"
            else:
                # Escape single quotes for SOQL safety
                safe_term = search_term.replace("'", "\\'")
                report_query = f"SELECT Id, Name, DeveloperName FROM Report WHERE Name LIKE '%{safe_term}%' LIMIT 20"
                
            try:
                reports = sf.query(report_query).get('records', [])
            except Exception as e:
                st.error(f"Failed to query Reports: {e}")
                reports = []

            if not reports:
                st.warning("No reports found matching that criteria.")
            else:
                st.success(f"Found {len(reports)} Report(s). Scanning for Dashboard hostiles...")
                
                # 2. Iterate through reports and find Dashboard dependencies
                all_results = []
                
                for rep in reports:
                    rep_id = rep['Id']
                    rep_name = rep['Name']
                    rep_link = f"https://{base_url}/lightning/r/Report/{rep_id}/view"
                    
                    dash_query = f"""
                        SELECT Id, DashboardId, Dashboard.Title, Dashboard.DeveloperName 
                        FROM DashboardComponent 
                        WHERE CustomReportId = '{rep_id}'
                    """
                    try:
                        dash_comps = sf.query(dash_query).get('records', [])
                    except Exception as e:
                        st.error(f"Failed to query Dashboard Components for {rep_name}: {e}")
                        continue
                        
                    if not dash_comps:
                        # No dependencies - Safe to delete!
                        all_results.append({
                            "Report Name": rep_name,
                            "Report Action": rep_link,
                            "Status": "🟢 SAFE TO DELETE",
                            "Hostage Dashboard": "None",
                            "Dashboard Action": "N/A",
                            "Component ID": "N/A"
                        })
                    else:
                        # Hostage situation found
                        for comp in dash_comps:
                            dash_id = comp.get('DashboardId')
                            dash_title = comp.get('Dashboard', {}).get('Title', 'Unknown Dashboard')
                            dash_link = f"https://{base_url}/lightning/r/Dashboard/{dash_id}/view"
                            
                            all_results.append({
                                "Report Name": rep_name,
                                "Report Action": rep_link,
                                "Status": "🔴 HELD HOSTAGE",
                                "Hostage Dashboard": dash_title,
                                "Dashboard Action": dash_link,
                                "Component ID": comp.get('Id')
                            })
                
                # 3. Render the Battleplan
                if all_results:
                    st.markdown("### 📋 Dependency Battleplan")
                    df_results = pd.DataFrame(all_results)
                    
                    # Metrics
                    safe_count = len(df_results[df_results['Status'] == '🟢 SAFE TO DELETE'])
                    hostage_count = len(df_results[df_results['Status'] == '🔴 HELD HOSTAGE'])
                    
                    m1, m2 = st.columns(2)
                    m1.metric("Reports Safe to Delete Immediately", safe_count)
                    m2.metric("Dependencies Blocking Deletion", hostage_count)
                    
                    st.markdown("---")
                    
                    # Slick DataFrame rendering with clickable links
                    st.dataframe(
                        df_results, 
                        use_container_width=True, 
                        hide_index=True,
                        height=min(600, max(150, len(df_results) * 35 + 40)),
                        column_config={
                            "Report Action": st.column_config.LinkColumn("Report Link", display_text="Open Report ↗"),
                            "Dashboard Action": st.column_config.LinkColumn("Dashboard Link", display_text="Open Dashboard ↗")
                        }
                    )
                    
                    # Fixed indentation: this now sits immediately after the table
                    st.info("**Ruthless Tip:** Click 'Open Dashboard' next to any 🔴 HELD HOSTAGE report. Edit the dashboard, delete the component referencing your report, save it, and then your report is free to be deleted.")

    # --- THE EXECUTIONER'S BLOCK ---
    st.markdown("---")
    st.subheader("🔥 The Executioner's Block")
    st.markdown("Use this to force-delete reports via the API when the Salesforce UI is blocked by broken filters, missing divisions, or invalid metadata.")
    
    col_del1, col_del2 = st.columns([3, 1])
    with col_del1:
        target_id = st.text_input("Target Report ID for Force Deletion:", max_chars=18)
    with col_del2:
        st.write("")
        st.write("")
        force_delete = st.button("Execute Hard Delete", type="primary", use_container_width=True)

    if force_delete and target_id:
        if not target_id.startswith('00O') or len(target_id) not in [15, 18]:
            st.error("Invalid Report ID. Must start with '00O' and be 15 or 18 characters.")
        else:
            with st.spinner("Executing direct API deletion..."):
                try:
                    # Bypasses the UI and sends a hard DELETE REST call to the record
                    sf.Report.delete(target_id)
                    st.success(f"Target neutralized: {target_id} has been permanently deleted from the system.")
                    st.balloons() # A little celebration for defeating Noah's mess
                except Exception as e:
                    st.error(f"The API failed to delete the record. Error: {e}")
