import streamlit as st
import pandas as pd
import urllib.parse
import re
from simple_salesforce import Salesforce

st.set_page_config(page_title="Ruthless Report Liberator", page_icon="🧨", layout="wide")

st.title("🧨 The Ruthless Report Liberator V12")
st.markdown("X-Ray the org for dependencies, extract entire folders of IDs, or mass-quarantine legacy garbage via Nuclear Lobotomy.")

# --- REUSABLE NUCLEAR LOBOTOMY ENGINE ---
def execute_nuclear_lobotomy(sf_instance, report_id, target_folder_id, target_name=None):
    """
    Obliterates all complex metadata from a corrupted report to bypass schema validation
    and forces it into a target folder.
    """
    raw_report = sf_instance.restful(f"analytics/reports/{report_id}")
    meta = raw_report.get("reportMetadata", {})
    
    # 1. Base Format & Columns
    meta["reportFormat"] = "TABULAR"
    
    # Safely handle detailColumns against NoneType returns
    detail_cols = meta.get("detailColumns")
    if isinstance(detail_cols, list) and len(detail_cols) > 0:
        meta["detailColumns"] = [detail_cols[0]]
    else:
        meta["detailColumns"] = []
        
    # 2. Obliterate Groupings, Filters, Aggregates, Buckets, and Cross Filters
    meta["groupingsDown"] = []
    meta["groupingsAcross"] = []
    meta["reportFilters"] = []
    meta["crossFilters"] = []
    meta["buckets"] = []
    meta["aggregates"] = []
    
    # 3. Purge invalid keys
    keys_to_nuke = [
        "reportBooleanFilter",
        "customSummaryFormula",
        "customSummaryFormulas",
        "customDetailFormulas",
        "reportChart",
        "chart"
    ]
    for key in keys_to_nuke:
        meta.pop(key, None)
        
    # 4. Force-Neutralize the Division Filter
    # Intercept null returns and force an empty list to prevent iteration crashes
    std_filters = meta.get("standardFilters")
    if not isinstance(std_filters, list):
        std_filters = []
        
    division_handled = False
    for f in std_filters:
        if isinstance(f, dict) and f.get("name") == "division":
            f["value"] = ""
            division_handled = True
            
    # If the division filter is missing entirely, we inject a blank one to force the overwrite
    if not division_handled:
        std_filters.append({"name": "division", "value": ""})
        
    meta["standardFilters"] = std_filters
                
    # Apply quarantine targets
    meta["folderId"] = target_folder_id
    if target_name:
        meta["name"] = target_name
        
    # Push the strict, schema-compliant empty shell to the server
    sf_instance.restful(f"analytics/reports/{report_id}", method="PATCH", json={"reportMetadata": meta})

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
            if 'cached_folders' in st.session_state:
                del st.session_state['cached_folders']
            st.success("Successfully connected to Salesforce.")
        except Exception as e:
            st.error(f"Connection failed: {e}")

# --- MAIN APP ---
if 'sf' in st.session_state:
    sf = st.session_state['sf']
    base_url = sf.sf_instance
    
    tab1, tab2, tab3 = st.tabs(["🎯 Single Target Hunter", "📁 Folder ID Harvester", "🗑️ Mass Quarantine Island"])
    
    # ==========================================
    # TAB 1: SINGLE TARGET HUNTER
    # ==========================================
    with tab1:
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
                    rep_id_15 = rep_id[:15] 
                    rep_name = rep['Name']
                    owner_id = rep.get('OwnerId', '')
                    rep_link = f"https://{base_url}/lightning/r/Report/{rep_id}/view"
                    
                    if owner_id.startswith('005'):
                        folder_link = "Private User Folder"
                    else:
                        folder_link = f"https://{base_url}/lightning/r/Folder/{owner_id}/view"
                    
                    dash_query = f"SELECT Id, DashboardId, Dashboard.Title FROM DashboardComponent WHERE CustomReportId = '{rep_id}'"
                    dash_comps = []
                    try: dash_comps = sf.query_all(dash_query).get('records', [])
                    except Exception: pass
                    
                    snap_query = f"SELECT Id, Name FROM AnalyticSnapshot WHERE ReportId = '{rep_id}'"
                    snaps = []
                    try: snaps = sf.query(snap_query).get('records', [])
                    except Exception: pass
                        
                    tooling_deps = []
                    try:
                        tooling_query = f"SELECT MetadataComponentName, MetadataComponentType FROM MetadataComponentDependency WHERE RefMetadataComponentId = '{rep_id_15}'"
                        encoded_query = urllib.parse.quote(tooling_query)
                        tooling_res = sf.toolingexecute(f"query/?q={encoded_query}")
                        tooling_deps = tooling_res.get('records', [])
                    except Exception: pass

                    if not dash_comps and not snaps and not tooling_deps:
                        all_results.append({
                            "Report Name": rep_name, "Report Action": rep_link, "Folder Link": folder_link,
                            "Status": "🟢 COMPLETELY CLEAN", "Hostage Location": "None", "Action Link": None, "Dependency Type": "N/A"
                        })
                    
                    for comp in dash_comps:
                        dash_id = comp.get('DashboardId')
                        dash_title = comp.get('Dashboard', {}).get('Title', 'Unknown (Likely Deleted)')
                        all_results.append({
                            "Report Name": rep_name, "Report Action": rep_link, "Folder Link": folder_link,
                            "Status": "🔴 HOSTAGE: DASHBOARD", "Hostage Location": dash_title, 
                            "Action Link": f"https://{base_url}/lightning/r/Dashboard/{dash_id}/view", "Dependency Type": "DashboardComponent"
                        })
                        
                    for snap in snaps:
                        all_results.append({
                            "Report Name": rep_name, "Report Action": rep_link, "Folder Link": folder_link,
                            "Status": "🔴 HOSTAGE: SNAPSHOT", "Hostage Location": snap.get('Name'),
                            "Action Link": f"https://{base_url}/lightning/setup/AnalyticSnapshots/home", "Dependency Type": "Reporting Snapshot"
                        })
                        
                    for dep in tooling_deps:
                        comp_type = dep.get('MetadataComponentType', 'Unknown')
                        comp_name = dep.get('MetadataComponentName', 'Unknown')
                        setup_link = f"https://{base_url}/lightning/setup/FlexiPage/home" if comp_type == 'FlexiPage' else f"https://{base_url}/lightning/setup/ObjectManager/home" if comp_type == 'Layout' else None
                        all_results.append({
                            "Report Name": rep_name, "Report Action": rep_link, "Folder Link": folder_link,
                            "Status": f"🔴 HOSTAGE: {comp_type.upper()}", "Hostage Location": comp_name,
                            "Action Link": setup_link, "Dependency Type": comp_type
                        })
            
                if all_results:
                    st.markdown("### 📋 Dependency Battleplan")
                    df_results = pd.DataFrame(all_results)
                    clean_count = len(df_results[df_results['Status'] == '🟢 COMPLETELY CLEAN'])
                    
                    m1, m2 = st.columns(2)
                    m1.metric("Reports Clean of Direct Links", clean_count)
                    m2.metric("Dependencies Found", len(df_results) - clean_count)
                    st.markdown("---")
                    
                    col_config = {
                        "Report Action": st.column_config.LinkColumn("Report Link", display_text="Open Report ↗"),
                        "Action Link": st.column_config.LinkColumn("Action Link", display_text="Investigate Hostage ↗")
                    }
                    if not any(df_results['Folder Link'] == 'Private User Folder'):
                        col_config["Folder Link"] = st.column_config.LinkColumn("Folder Link", display_text="Open Folder Settings ↗")
                    
                    st.dataframe(df_results, use_container_width=True, hide_index=True, column_config=col_config)

        # --- THE EXECUTIONER'S BLOCK ---
        st.markdown("---")
        st.subheader("🔥 The Executioner's Block")
        
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

        if force_move and target_id:
            if not target_id.startswith('00O') or len(target_id) not in [15, 18]: st.error("Invalid Report ID.")
            else:
                with st.spinner("Locating Organization ID..."):
                    try:
                        org_id = sf.query("SELECT Id FROM Organization")['records'][0]['Id']
                        # POLITE ATTEMPT FIRST
                        payload = {"reportMetadata": {"folderId": org_id}}
                        sf.restful(f"analytics/reports/{target_id}", method="PATCH", json=payload)
                        st.success("Trojan Horse successful! Report moved to Unfiled Public Reports. Now click Hard Delete.")
                    except Exception:
                        # NUCLEAR ESCALATION
                        try:
                            execute_nuclear_lobotomy(sf, target_id, org_id)
                            st.success("Trojan Horse successful via Nuclear Lobotomy. Broken layout wiped to force move.")
                        except Exception as e: st.error(f"Total failure on Trojan Horse. Error: {e}")

        if force_delete and target_id:
            if not target_id.startswith('00O') or len(target_id) not in [15, 18]: st.error("Invalid Report ID.")
            else:
                with st.spinner("Executing direct API deletion..."):
                    try:
                        sf.Report.delete(target_id)
                        st.success(f"Target neutralized: {target_id} has been permanently deleted from the system.")
                        st.balloons() 
                    except Exception as e: st.error(f"The API failed to delete the record. Error: {e}")

        if force_quarantine and target_id:
            if not target_id.startswith('00O') or len(target_id) not in [15, 18]: st.error("Invalid Report ID.")
            else:
                with st.spinner("Executing Quarantine..."):
                    try:
                        folder_records = sf.query("SELECT Id FROM Folder WHERE DeveloperName = 'ZZZDONOTUSETRASH'")['records']
                        if not folder_records: st.error("Could not find folder API Name 'ZZZDONOTUSETRASH'.")
                        else:
                            trash_folder_id = folder_records[0]['Id']
                            new_name = f"DEAD REPORT - {target_id}"[:40] 
                            
                            # POLITE ATTEMPT FIRST
                            try:
                                payload = {"reportMetadata": {"folderId": trash_folder_id, "name": new_name}}
                                sf.restful(f"analytics/reports/{target_id}", method="PATCH", json=payload)
                                st.success(f"Banishment complete. {target_id} has been exiled and renamed.")
                            except Exception:
                                # NUCLEAR ESCALATION
                                try:
                                    execute_nuclear_lobotomy(sf, target_id, trash_folder_id, new_name)
                                    st.warning(f"Banishment complete via Nuclear Lobotomy. Corrupt schema was wiped to force the rename and move.")
                                except Exception as e:
                                    st.error(f"Total Quarantine Failure. Error: {e}")
                    except Exception as e: st.error(f"Failed to quarantine. Error: {e}")

    # ==========================================
    # TAB 2: FOLDER ID HARVESTER
    # ==========================================
    with tab2:
        st.subheader("📁 Folder ID Harvester")
        if 'cached_folders' not in st.session_state:
            with st.spinner("Mapping org folders..."):
                try:
                    folder_res = sf.query("SELECT Id, Name, DeveloperName FROM Folder WHERE Type = 'Report' ORDER BY Name ASC")['records']
                    folder_options = [{"label": f"📦 {f['Name']} ({f['DeveloperName']})", "id": f['Id']} for f in folder_res]
                    st.session_state['cached_folders'] = folder_options
                except Exception as e:
                    st.error(f"Failed to load folders: {e}")
                    st.session_state['cached_folders'] = []
                    
        folders = st.session_state.get('cached_folders', [])
        
        if folders:
            folder_map = {f['label']: f['id'] for f in folders}
            selected_folder_label = st.selectbox("Select Target Report Folder to Scan:", list(folder_map.keys()))
            selected_folder_id = folder_map[selected_folder_label]
            
            if st.button("Harvest Report IDs", type="primary"):
                with st.spinner("Harvesting records..."):
                    try:
                        reports_in_folder = sf.query(f"SELECT Id, Name FROM Report WHERE OwnerId = '{selected_folder_id}' ORDER BY Name ASC")['records']
                        if not reports_in_folder: st.warning("This folder is empty or contains no queryable custom reports.")
                        else:
                            st.success(f"Successfully harvested {len(reports_in_folder)} report(s) from this folder!")
                            folder_data = [{"Report Name": r['Name'], "Report ID": r['Id']} for r in reports_in_folder]
                            st.dataframe(pd.DataFrame(folder_data), use_container_width=True, hide_index=True)
                            raw_id_list = ", ".join([r['Id'] for r in reports_in_folder])
                            st.markdown("### 📋 Copypasta Output")
                            st.text_area("Raw ID Text Block:", value=raw_id_list, height=150)
                    except Exception as e: st.error(f"Failed to extract records: {e}")

    # ==========================================
    # TAB 3: MASS QUARANTINE ISLAND
    # ==========================================
    with tab3:
        st.subheader("🗑️ Bulk Quarantine Engine")
        st.markdown("""
        Paste a list of raw Report IDs below. The engine will:
        1. Extract the valid `00O...` IDs.
        2. Attempt standard Analytics API move and rename.
        3. If blocked by validation errors, the **Nuclear Lobotomy** will wipe the report structure completely blank to force the process through.
        """)
        
        bulk_ids_input = st.text_area("Paste Report IDs (comma separated, newlines, or a raw list):", height=200)
        
        if st.button("Execute Mass Quarantine", type="primary"):
            if bulk_ids_input:
                raw_ids = re.findall(r'00O[a-zA-Z0-9]{12,15}', bulk_ids_input)
                unique_ids = list(set(raw_ids))
                
                if not unique_ids:
                    st.warning("No valid Report IDs found in your input.")
                else:
                    try:
                        folder_records = sf.query("SELECT Id FROM Folder WHERE DeveloperName = 'ZZZDONOTUSETRASH'")['records']
                        if not folder_records:
                            st.error("Could not find the 'ZZZDONOTUSETRASH' folder.")
                        else:
                            trash_folder_id = folder_records[0]['Id']
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            results = []
                            
                            for i, r_id in enumerate(unique_ids):
                                status_text.text(f"Quarantining {i+1} of {len(unique_ids)}: {r_id}...")
                                new_name = f"DEAD REPORT - {r_id}"[:40]
                                
                                # STEP 1: Polite Standard Method
                                try:
                                    payload = {"reportMetadata": {"name": new_name, "folderId": trash_folder_id}}
                                    sf.restful(f"analytics/reports/{r_id}", method="PATCH", json=payload)
                                    results.append({"Report ID": r_id, "Status": "✅ Banished & Renamed", "Error": ""})
                                except Exception:
                                    # STEP 2: The Nuclear Lobotomy Escalation
                                    try:
                                        execute_nuclear_lobotomy(sf, r_id, trash_folder_id, new_name)
                                        results.append({"Report ID": r_id, "Status": "⚠️ Lobotomized & Banished", "Error": "Corrupted. Layout completely wiped to force action."})
                                    except Exception as lobotomy_err:
                                        results.append({"Report ID": r_id, "Status": "❌ Total Failure", "Error": str(lobotomy_err)})
                                
                                progress_bar.progress((i + 1) / len(unique_ids))
                                
                            status_text.text("Mass Quarantine Complete.")
                            df_bulk = pd.DataFrame(results)
                            st.dataframe(df_bulk, use_container_width=True, hide_index=True)
                            
                    except Exception as e:
                        st.error(f"System error during bulk operation: {e}")
            else:
                st.warning("Please paste some IDs first.")
