import streamlit as st
import pandas as pd
import urllib.parse
from simple_salesforce import Salesforce

st.set_page_config(page_title="Ruthless Report Liberator", page_icon="🧨", layout="wide")

st.title("🧨 The Ruthless Report Liberator V5")
st.markdown("X-Ray the org for Dashboards, Snapshots, FlexiPages, and Layouts holding your reports hostage.")

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
        with st.spinner("Executing Deep Metadata Scan..."):
            # 1. Fetch the Reports
            is_id = search_term.startswith('00O') and len(search_term) in [15, 18]
            
            if is_id:
                report_query = f"SELECT Id, Name, DeveloperName, OwnerId FROM Report WHERE Id = '{search_term}'"
            else:
                safe_term = search_term.replace("'", "\\'")
                report_query = f"SELECT Id, Name, DeveloperName, OwnerId FROM Report WHERE Name LIKE '%{safe_term}%' LIMIT 20"
                
            try:
                reports = sf.query(report_query).get('records', [])
            except Exception as e:
                st.error(f"Failed to query Reports: {e}")
                reports = []

            if not reports:
                st.warning("No reports found matching that criteria.")
            else:
                st.success(f"Found {len(reports)} Report(s). Initiating deep scan...")
                
                all_results = []
                
                for rep in reports:
                    rep_id = rep['Id']
                    # The Tooling API needs the 15-character ID for dependency tracking
                    rep_id_15 = rep_id[:15] 
                    rep_name = rep['Name']
                    owner_id = rep.get('OwnerId', '')
                    rep_link = f"https://{base_url}/lightning/r/Report/{rep_id}/view"
                    
                    if owner_id.startswith('005'):
                        folder_link = "Private User Folder"
                    else:
                        folder_link = f"https://{base_url}/lightning/r/Folder/{owner_id}/view"
                    
                    # HUNT 1: Dashboards (Including Recycle Bin)
                    dash_query = f"SELECT Id, DashboardId, Dashboard.Title FROM DashboardComponent WHERE CustomReportId = '{rep_id}'"
                    dash_comps = []
                    try:
                        dash_comps = sf.query_all(dash_query).get('records', [])
                    except Exception as e:
                        pass
                    
                    # HUNT 2: Analytic Snapshots
                    snap_query = f"SELECT Id, Name FROM AnalyticSnapshot WHERE ReportId = '{rep_id}'"
                    snaps = []
                    try:
                        snaps = sf.query(snap_query).get('records', [])
                    except Exception as e:
                        pass
                        
                    # HUNT 3: Tooling API (FlexiPages & Layouts)
                    tooling_deps = []
                    try:
                        tooling_query = f"SELECT MetadataComponentName, MetadataComponentType FROM MetadataComponentDependency WHERE RefMetadataComponentId = '{rep_id_15}'"
                        encoded_query = urllib.parse.quote(tooling_query)
                        tooling_res = sf.toolingexecute(f"query/?q={encoded_query}")
                        tooling_deps = tooling_res.get('records', [])
                    except Exception as e:
                        pass

                    # Compile Results
                    if not dash_comps and not snaps and not tooling_deps:
                        all_results.append({
                            "Report Name": rep_name,
                            "Report Action": rep_link,
                            "Folder Link": folder_link,
                            "Status": "🟢 COMPLETELY CLEAN",
                            "Hostage Location": "None",
                            "Action Link": None,
                            "Dependency Type": "N/A"
                        })
                    
                    for comp in dash_comps:
                        dash_id = comp.get('DashboardId')
                        dash_title = comp.get('Dashboard', {}).get('Title', 'Unknown (Likely Deleted)')
                        all_results.append({
                            "Report Name": rep_name,
                            "Report Action": rep_link,
                            "Folder Link": folder_link,
                            "Status": "🔴 HOSTAGE: DASHBOARD",
                            "Hostage Location": dash_title,
                            "Action Link": f"https://{base_url}/lightning/r/Dashboard/{dash_id}/view",
                            "Dependency Type": "DashboardComponent"
                        })
                        
                    for snap in snaps:
                        all_results.append({
                            "Report Name": rep_name,
                            "Report Action": rep_link,
                            "Folder Link": folder_link,
                            "Status": "🔴 HOSTAGE: SNAPSHOT",
                            "Hostage Location": snap.get('Name'),
                            "Action Link": f"https://{base_url}/lightning/setup/AnalyticSnapshots/home",
                            "Dependency Type": "Reporting Snapshot"
                        })
                        
                    for dep in tooling_deps:
                        comp_type = dep.get('MetadataComponentType', 'Unknown')
                        comp_name = dep.get('MetadataComponentName', 'Unknown')
                        
                        # Route the Action Link based on the Metadata Type
                        setup_link = None
                        if comp_type == 'FlexiPage':
                            setup_link = f"https://{base_url}/lightning/setup/FlexiPage/home"
                        elif comp_type == 'Layout':
                            setup_link = f"https://{base_url}/lightning/setup/ObjectManager/home"
                            
                        all_results.append({
                            "Report Name": rep_name,
                            "Report Action": rep_link,
                            "Folder Link": folder_link,
                            "Status": f"🔴 HOSTAGE: {comp_type.upper()}",
                            "Hostage Location": comp_name,
                            "Action Link": setup_link,
                            "Dependency Type": comp_type
                        })
                
                # Render Battleplan
                if all_results:
                    st.markdown("### 📋 Dependency Battleplan")
                    df_results = pd.DataFrame(all_results)
                    
                    clean_count = len(df_results[df_results['Status'] == '🟢 COMPLETELY CLEAN'])
                    hostage_count = len(df_results) - clean_count
                    
                    m1, m2 = st.columns(2)
                    m1.metric("Reports Clean of Direct Links", clean_count)
                    m2.metric("Dependencies Found", hostage_count)
                    
                    st.markdown("---")
                    
                    col_config = {
                        "Report Action": st.column_config.LinkColumn("Report Link", display_text="Open Report ↗"),
                        "Action Link": st.column_config.LinkColumn("Action Link", display_text="Investigate Hostage ↗")
                    }
                    
                    if not any(df_results['Folder Link'] == 'Private User Folder'):
                        col_config["Folder Link"] = st.column_config.LinkColumn("Folder Link", display_text="Open Folder Settings ↗")
                    
                    st.dataframe(
                        df_results, 
                        use_container_width=True, hide_index=True,
                        height=min(600, max(150, len(df_results) * 35 + 40)),
                        column_config=col_config
                    )
                    
                    st.info("**Ruthless Tip:** If a FlexiPage is listed, click 'Investigate Hostage' to go to the Lightning App Builder, find that page name, edit it, and remove the Report Chart component.")


    # --- THE EXECUTIONER'S BLOCK ---
    st.markdown("---")
    st.subheader("🔥 The Executioner's Block")
    st.markdown("Force-delete reports via the API, restore broken security contexts via Trojan Horse, or banish them to the Quarantine folder forever.")
    
    col_del1, col_del2 = st.columns([1.5, 2.5])
    with col_del1:
        target_id = st.text_input("Target Report ID for Action:", max_chars=18)
    with col_del2:
        st.write("")
        st.write("")
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            force_move = st.button("1. Trojan Horse", use_container_width=True)
        with col_btn2:
            force_delete = st.button("2. Hard Delete", type="primary", use_container_width=True)
        with col_btn3:
            force_quarantine = st.button("3. Quarantine to Island", use_container_width=True)

    # ACTION 1: The Trojan Horse (Fixing Orphaned Reports)
    if force_move and target_id:
        if not target_id.startswith('00O') or len(target_id) not in [15, 18]:
            st.error("Invalid Report ID.")
        else:
            with st.spinner("Locating Organization ID..."):
                try:
                    # The absolute true ID of the "Unfiled Public Reports" folder is the Org ID
                    org_query = "SELECT Id FROM Organization"
                    org_id = sf.query(org_query)['records'][0]['Id']
                    
                    # Force the report into the public folder to restore security context
                    sf.Report.update(target_id, {'OwnerId': org_id})
                    st.success("Trojan Horse successful! Report moved to Unfiled Public Reports. Now click Hard Delete.")
                except Exception as e:
                    st.error(f"Failed to move report. Error: {e}")

    # ACTION 2: The Kill Switch
    if force_delete and target_id:
        if not target_id.startswith('00O') or len(target_id) not in [15, 18]:
            st.error("Invalid Report ID.")
        else:
            with st.spinner("Executing direct API deletion..."):
                try:
                    sf.Report.delete(target_id)
                    st.success(f"Target neutralized: {target_id} has been permanently deleted from the system.")
                    st.balloons() 
                except Exception as e:
                    st.error(f"The API failed to delete the record. Error: {e}")

    # ACTION 3: The Quarantine (Banish to ZZZDONOTUSETRASH)
    if force_quarantine and target_id:
        if not target_id.startswith('00O') or len(target_id) not in [15, 18]:
            st.error("Invalid Report ID.")
        else:
            with st.spinner("Locating Quarantine Island (ZZZDONOTUSETRASH)..."):
                try:
                    # Find the exact ID of your trash folder
                    folder_query = "SELECT Id FROM Folder WHERE DeveloperName = 'ZZZDONOTUSETRASH'"
                    folder_records = sf.query(folder_query)['records']
                    
                    if not folder_records:
                        st.error("Could not find a folder with the exact API Name 'ZZZDONOTUSETRASH'. Make sure it exists and you have access to it.")
                    else:
                        trash_folder_id = folder_records[0]['Id']
                        
                        # Move the report to the trash folder
                        sf.Report.update(target_id, {'OwnerId': trash_folder_id})
                        st.success(f"Banishment complete. {target_id} has been exiled to the ZZZDONOTUSETRASH folder.")
                except Exception as e:
                    st.error(f"Failed to quarantine the report. Error: {e}")
