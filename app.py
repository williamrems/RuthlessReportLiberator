import streamlit as st
import pandas as pd
import urllib.parse
import re
import json
from simple_salesforce import Salesforce

st.set_page_config(page_title="Ruthless Report Liberator", page_icon="🧨", layout="wide")

st.title("🧨 The Ruthless Report Liberator V28")
st.markdown("X-Ray the org for dependencies, extract entire folders of IDs, or mass-quarantine legacy garbage via Atomic Decoupling.")

# === HARDCODED KILL LIST ===
DEAD_DIVISIONS = [
    "Madison, WI",
    "Neenah, WI",
    "Granger, IA",
    "Omaha, NE",
    "Tulsa, OK",
    "Grand Rapids, MI"
]

# === ATOMIC HELPER FUNCTIONS ===
def clean_report_json(raw_dict):
    """
    Dynamically hunts down corrupt divisions and their URL-encoded variants
    using a hardcoded kill list to bypass initial JSON validation.
    """
    meta_str = json.dumps(raw_dict)
    
    for bad_div in DEAD_DIVISIONS:
        # 1. Replace the exact raw string
        meta_str = meta_str.replace(bad_div, "Baldwin")
        
        # 2. Replace the URL-encoded comma variant (e.g., Tulsa%2C OK)
        encoded_div = bad_div.replace(",", "%2C")
        meta_str = meta_str.replace(encoded_div, "Baldwin")
        
        # 3. Replace just the city prefix if it is dangling
        city_only = bad_div.split(',')[0].strip()
        meta_str = meta_str.replace(city_only, "Baldwin")
        
    meta = json.loads(meta_str)
    
    # Force the standard filter just to guarantee compliance
    if "standardFilters" in meta:
        for f in meta["standardFilters"]:
            if isinstance(f, dict) and str(f.get("name", "")).lower() == "division":
                f["value"] = "Baldwin"
                
    return meta

def gut_report_metadata(meta):
    """
    Surgically removes buckets and formulas to prevent dependency paradoxes during rename.
    """
    if "buckets" in meta: 
        meta["buckets"] = []
    if "customSummaryFormulas" in meta: 
        meta["customSummaryFormulas"] = []
    if "customDetailFormulas" in meta: 
        meta["customDetailFormulas"] = []
        
    list_keys = ["detailColumns", "groupingsDown", "groupingsAcross", "sortBy", "aggregates"]
    for k in list_keys:
        if k in meta and isinstance(meta[k], list):
            meta[k] = [x for x in meta[k] if "BucketField" not in str(x) and "FORMULA" not in str(x)]
            
    meta.pop("reportChart", None)
    meta.pop("chart", None)
    meta.pop("hasChart", None)
    return meta

# === SIDEBAR: AUTHENTICATION ===
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

# === MAIN APP ===
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

        # ==========================================
        # THE EXECUTIONER'S BLOCK
        # ==========================================
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
                exec_move = st.button("1. Trojan Horse", use_container_width=True)
            with col_btn2:
                exec_delete = st.button("2. Hard Delete", type="primary", use_container_width=True)
            with col_btn3:
                exec_quarantine = st.button("3. Quarantine to Island", use_container_width=True)

        if exec_move and target_id:
            if not target_id.startswith('00O') or len(target_id) not in [15, 18]: st.error("Invalid Report ID.")
            else:
                with st.spinner("Locating Organization ID and executing move..."):
                    try:
                        org_id = sf.query("SELECT Id FROM Organization")['records'][0]['Id']
                        move_success = False
                        
                        try:
                            sf.Report.update(target_id, {"OwnerId": org_id})
                            move_success = True
                        except Exception:
                            try:
                                raw_report = sf.restful(f"analytics/reports/{target_id}")
                                meta = clean_report_json(raw_report.get("reportMetadata", {}))
                                meta["folderId"] = org_id
                                sf.restful(f"analytics/reports/{target_id}", method="PATCH", json={"reportMetadata": meta})
                                move_success = True
                            except Exception as e:
                                st.error(f"Total failure on isolated move. Error: {e}")
                                
                        if move_success:
                            st.success("Trojan Horse isolated move successful! Report moved to Unfiled Public Reports. Now click Hard Delete.")
                    except Exception as e: 
                        st.error(f"Failed to query Org ID. Error: {e}")

        if exec_delete and target_id:
            if not target_id.startswith('00O') or len(target_id) not in [15, 18]: st.error("Invalid Report ID.")
            else:
                with st.spinner("Executing direct API deletion..."):
                    try:
                        sf.Report.delete(target_id)
                        st.success(f"Target neutralized: {target_id} has been permanently deleted from the system.")
                        st.balloons() 
                    except Exception as e: st.error(f"The API failed to delete the record. Error: {e}")

        if exec_quarantine and target_id:
            if not target_id.startswith('00O') or len(target_id) not in [15, 18]: st.error("Invalid Report ID.")
            else:
                with st.spinner("Executing Atomic Quarantine..."):
                    try:
                        folder_records = sf.query("SELECT Id FROM Folder WHERE DeveloperName = 'ZZZDONOTUSETRASH'")['records']
                        if not folder_records: st.error("Could not find folder API Name 'ZZZDONOTUSETRASH'.")
                        else:
                            trash_folder_id = folder_records[0]['Id']
                            new_name = f"DEAD REPORT - TRASH - {target_id}"[:40] 
                            
                            # PHASE 1: ISOLATED MOVE
                            move_success = False
                            try:
                                sf.Report.update(target_id, {"OwnerId": trash_folder_id})
                                move_success = True
                            except Exception:
                                try:
                                    raw_report = sf.restful(f"analytics/reports/{target_id}")
                                    meta = clean_report_json(raw_report.get("reportMetadata", {}))
                                    meta["folderId"] = trash_folder_id
                                    sf.restful(f"analytics/reports/{target_id}", method="PATCH", json={"reportMetadata": meta})
                                    move_success = True
                                except Exception as e:
                                    st.error(f"Phase 1 Failure: Report could not be moved to the folder. Error: {e}")

                            # PHASE 2: DECOUPLED RENAME & GUT
                            if move_success:
                                try:
                                    sf.Report.update(target_id, {"Name": new_name})
                                    st.success(f"Banishment complete. {target_id} successfully moved and renamed.")
                                except Exception:
                                    try:
                                        raw_report = sf.restful(f"analytics/reports/{target_id}")
                                        meta = clean_report_json(raw_report.get("reportMetadata", {}))
                                        meta = gut_report_metadata(meta)
                                        meta["name"] = new_name
                                        sf.restful(f"analytics/reports/{target_id}", method="PATCH", json={"reportMetadata": meta})
                                        st.warning(f"Banishment complete via Gut Engine. {target_id} moved and renamed.")
                                    except Exception as e:
                                        st.warning(f"Partial Banishment. {target_id} was successfully moved to the island folder, but structural corruption blocked the rename operation. It is contained.")
                    except Exception as e: st.error(f"Failed to query target folder. Error: {e}")

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
        2. Execute an **Isolated Move** to guarantee the report reaches the island folder.
        3. Only after confirming the move, execute a **Decoupled Rename & Gut**. If the report schema completely locks down the rename, it remains safely contained on the island.
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
                                new_name = f"DEAD REPORT - TRASH - {r_id}"[:40]
                                
                                # PHASE 1: ISOLATED MOVE
                                move_success = False
                                error_log = ""
                                try:
                                    sf.Report.update(r_id, {"OwnerId": trash_folder_id})
                                    move_success = True
                                except Exception:
                                    try:
                                        raw_report = sf.restful(f"analytics/reports/{r_id}")
                                        meta = clean_report_json(raw_report.get("reportMetadata", {}))
                                        meta["folderId"] = trash_folder_id
                                        sf.restful(f"analytics/reports/{r_id}", method="PATCH", json={"reportMetadata": meta})
                                        move_success = True
                                    except Exception as e:
                                        error_log = f"Move strictly locked by Salesforce. Error: {e}"

                                # PHASE 2: DECOUPLED RENAME & GUT
                                if move_success:
                                    try:
                                        sf.Report.update(r_id, {"Name": new_name})
                                        results.append({"Report ID": r_id, "Status": "✅ Banished & Renamed", "Error": ""})
                                    except Exception:
                                        try:
                                            raw_report = sf.restful(f"analytics/reports/{r_id}")
                                            meta = clean_report_json(raw_report.get("reportMetadata", {}))
                                            meta = gut_report_metadata(meta)
                                            meta["name"] = new_name
                                            sf.restful(f"analytics/reports/{r_id}", method="PATCH", json={"reportMetadata": meta})
                                            results.append({"Report ID": r_id, "Status": "✅ Banished, Gutted & Renamed", "Error": ""})
                                        except Exception as e:
                                            results.append({"Report ID": r_id, "Status": "⚠️ Banished (Rename Locked)", "Error": "Moved to island, but corrupt schema blocked rename."})
                                else:
                                    results.append({"Report ID": r_id, "Status": "❌ Move Failed", "Error": error_log})
                                
                                progress_bar.progress((i + 1) / len(unique_ids))
                                
                            status_text.text("Mass Quarantine Complete.")
                            df_bulk = pd.DataFrame(results)
                            st.dataframe(df_bulk, use_container_width=True, hide_index=True)
                            
                    except Exception as e:
                        st.error(f"System error during bulk operation: {e}")
            else:
                st.warning("Please paste some IDs first.")
