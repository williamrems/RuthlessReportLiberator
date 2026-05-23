import streamlit as st
import pandas as pd
import urllib.parse
import re
import json
from simple_salesforce import Salesforce

st.set_page_config(page_title="Ruthless Report Liberator", page_icon="🧨", layout="wide")

st.title("🧨 The Ruthless Report Liberator V33")
st.markdown("X-Ray the org for dependencies, mass-quarantine legacy garbage, sever zombie links, and execute ghost dashboards.")

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
        
        # 2. Replace the URL-encoded comma variant
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
    
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🎯 Single Target Hunter", 
        "📁 Folder Harvester", 
        "🗑️ Quarantine Island", 
        "🪹 Empty Report Folders", 
        "📊 Empty Dashboard Folders",
        "🧟 Zombie Hunter",
        "👻 Ghost Dashboard Slayer"
    ])
    
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
                            error_log = ""
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
                                    error_log = f"Move strictly locked by Salesforce. Error: {e}"

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
                            else:
                                st.error(f"Phase 1 Failure: Report could not be moved to the folder. {error_log}")
                    except Exception as e: st.error(f"Failed to query target folder. Error: {e}")

    # ==========================================
    # TAB 2: FOLDER ID HARVESTER
    # ==========================================
    with tab2:
        st.subheader("📁 Folder ID Harvester")
        if 'cached_folders' not in st.session_state:
            with st.spinner("Mapping org folders..."):
                try:
                    folder_res = sf.query_all("SELECT Id, Name, DeveloperName FROM Folder WHERE Type = 'Report' ORDER BY Name ASC")['records']
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
                        reports_in_folder = sf.query_all(f"SELECT Id, Name FROM Report WHERE OwnerId = '{selected_folder_id}' ORDER BY Name ASC")['records']
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
        3. Only after confirming the move, execute a **Decoupled Rename & Gut**.
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

    # ==========================================
    # TAB 4: EMPTY REPORT FOLDER RADAR
    # ==========================================
    with tab4:
        st.subheader("🪹 Empty Report Folder Radar")
        st.markdown("Scan your org's Report Folders to identify empty directories. Recursively counts all nested contents.")
        
        if st.button("Run Report Folder Audit", type="primary"):
            with st.spinner("Mapping folders and calculating recursive rollups..."):
                try:
                    folders = sf.query_all("SELECT Id, Name, DeveloperName, ParentId FROM Folder WHERE Type = 'Report'")['records']
                    reports = sf.query_all("SELECT Id, OwnerId FROM Report")['records']
                    
                    df_reports = pd.DataFrame(reports)
                    count_map = df_reports['OwnerId'].value_counts().to_dict() if not df_reports.empty else {}

                    folder_dict = {}
                    for f in folders:
                        folder_dict[f['Id']] = {
                            "Folder Name": f['Name'],
                            "Developer Name": f['DeveloperName'],
                            "ParentId": f.get('ParentId'),
                            "Direct Count": count_map.get(f['Id'], 0),
                            "Total Count": 0,
                            "Children": [],
                            "Folder Link": f"https://{base_url}/lightning/r/Folder/{f['Id']}/view"
                        }

                    for f_id, data in folder_dict.items():
                        p_id = data["ParentId"]
                        if p_id and p_id in folder_dict:
                            folder_dict[p_id]["Children"].append(f_id)

                    computed = set()
                    def get_rollup(fid):
                        if fid in computed:
                            return folder_dict[fid]["Total Count"]
                        total = folder_dict[fid]["Direct Count"]
                        for cid in folder_dict[fid]["Children"]:
                            total += get_rollup(cid)
                        folder_dict[fid]["Total Count"] = total
                        computed.add(fid)
                        return total

                    folder_data = []
                    for f_id, data in folder_dict.items():
                        get_rollup(f_id)
                        folder_data.append({
                            "Folder Name": data["Folder Name"],
                            "Developer Name": data["Developer Name"],
                            "Total Nested Reports": data["Total Count"],
                            "Direct Reports": data["Direct Count"],
                            "Subfolders": len(data["Children"]),
                            "Folder Link": data["Folder Link"]
                        })

                    if not folder_data:
                        st.info("No custom report folders found in this org.")
                    else:
                        df_folders = pd.DataFrame(folder_data)
                        df_folders = df_folders.sort_values(by="Total Nested Reports", ascending=True)
                        
                        empty_count = len(df_folders[df_folders['Total Nested Reports'] == 0])
                        st.success(f"Audit Complete! Scanned {len(folders)} total folders. Found {empty_count} completely empty folders.")

                        col_config = {
                            "Folder Link": st.column_config.LinkColumn("Action", display_text="Open Folder ↗")
                        }
                        st.dataframe(df_folders, use_container_width=True, hide_index=True, column_config=col_config)

                except Exception as e:
                    st.error(f"Failed to scan folders. Error: {e}")

    # ==========================================
    # TAB 5: EMPTY DASHBOARD FOLDER RADAR
    # ==========================================
    with tab5:
        st.subheader("📊 Empty Dashboard Folder Radar")
        st.markdown("Scan your org's Dashboard Folders to identify empty directories. Recursively counts all nested contents.")
        
        if st.button("Run Dashboard Folder Audit", type="primary"):
            with st.spinner("Mapping dashboard folders and calculating recursive rollups..."):
                try:
                    folders = sf.query_all("SELECT Id, Name, DeveloperName, ParentId FROM Folder WHERE Type = 'Dashboard'")['records']
                    dashboards = sf.query_all("SELECT Id, FolderId FROM Dashboard")['records']
                    
                    df_dashboards = pd.DataFrame(dashboards)
                    count_map = df_dashboards['FolderId'].value_counts().to_dict() if not df_dashboards.empty else {}

                    folder_dict = {}
                    for f in folders:
                        folder_dict[f['Id']] = {
                            "Folder Name": f['Name'],
                            "Developer Name": f['DeveloperName'],
                            "ParentId": f.get('ParentId'),
                            "Direct Count": count_map.get(f['Id'], 0),
                            "Total Count": 0,
                            "Children": [],
                            "Folder Link": f"https://{base_url}/lightning/r/Folder/{f['Id']}/view"
                        }

                    for f_id, data in folder_dict.items():
                        p_id = data["ParentId"]
                        if p_id and p_id in folder_dict:
                            folder_dict[p_id]["Children"].append(f_id)

                    computed = set()
                    def get_rollup(fid):
                        if fid in computed:
                            return folder_dict[fid]["Total Count"]
                        total = folder_dict[fid]["Direct Count"]
                        for cid in folder_dict[fid]["Children"]:
                            total += get_rollup(cid)
                        folder_dict[fid]["Total Count"] = total
                        computed.add(fid)
                        return total

                    folder_data = []
                    for f_id, data in folder_dict.items():
                        get_rollup(f_id)
                        folder_data.append({
                            "Folder Name": data["Folder Name"],
                            "Developer Name": data["Developer Name"],
                            "Total Nested Dashboards": data["Total Count"],
                            "Direct Dashboards": data["Direct Count"],
                            "Subfolders": len(data["Children"]),
                            "Folder Link": data["Folder Link"]
                        })

                    if not folder_data:
                        st.info("No custom dashboard folders found in this org.")
                    else:
                        df_folders = pd.DataFrame(folder_data)
                        df_folders = df_folders.sort_values(by="Total Nested Dashboards", ascending=True)
                        
                        empty_count = len(df_folders[df_folders['Total Nested Dashboards'] == 0])
                        st.success(f"Audit Complete! Scanned {len(folders)} total folders. Found {empty_count} completely empty dashboard folders.")

                        col_config = {
                            "Folder Link": st.column_config.LinkColumn("Action", display_text="Open Folder ↗")
                        }
                        st.dataframe(df_folders, use_container_width=True, hide_index=True, column_config=col_config)

                except Exception as e:
                    st.error(f"Failed to scan dashboard folders. Error: {e}")

    # ==========================================
    # TAB 6: ZOMBIE DASHBOARD HUNTER
    # ==========================================
    with tab6:
        st.subheader("🧟 Zombie Dashboard Hunter")
        st.markdown("Cross-reference all dashboards against your quarantined reports to find out which ones are holding your trash hostage. Output the results to CSV.")
        
        col_z1, col_z2 = st.columns([3, 1])
        with col_z1:
            audit_type = st.radio("Audit Scope:", ["Show Only TRASH/DEAD REPORTS (Hostage Rescue)", "Map ALL Dashboards to ALL Reports"])
        with col_z2:
            st.write("")
            st.write("")
            run_zombie = st.button("Run Dependency Audit", type="primary", use_container_width=True)
            
        if run_zombie:
            with st.spinner("Executing bulk cross-reference matrix..."):
                try:
                    # 1. Fetch Dashboard Components
                    dash_comps = sf.query_all("SELECT DashboardId, Dashboard.Title, CustomReportId FROM DashboardComponent WHERE CustomReportId != null")['records']
                    
                    if not dash_comps:
                        st.success("No dashboard components found linked to reports.")
                    else:
                        df_dash = pd.DataFrame(dash_comps)
                        df_dash['Dashboard Name'] = df_dash['Dashboard'].apply(lambda x: x['Title'] if x else 'Unknown')
                        df_dash = df_dash.drop(columns=['Dashboard', 'attributes'])
                        df_dash['MergeId'] = df_dash['CustomReportId'].str[:15]
                        
                        # 2. Fetch Reports based on scope using flat FolderName
                        if "TRASH" in audit_type:
                            query_reports = "SELECT Id, Name, FolderName FROM Report WHERE Name LIKE '%TRASH%' OR Name LIKE '%DEAD REPORT%'"
                        else:
                            query_reports = "SELECT Id, Name, FolderName FROM Report"
                            
                        reports = sf.query_all(query_reports)['records']
                        
                        if not reports:
                            st.success("No reports found matching the criteria.")
                        else:
                            df_reports = pd.DataFrame(reports)
                            df_reports = df_reports.rename(columns={'Id': 'ReportId', 'Name': 'Report Name', 'FolderName': 'Folder Name'})
                            if 'attributes' in df_reports.columns:
                                df_reports = df_reports.drop(columns=['attributes'])
                            df_reports['MergeId'] = df_reports['ReportId'].str[:15]
                            
                            # 3. Fast Matrix Merge
                            df_matrix = pd.merge(df_reports, df_dash, on='MergeId', how='inner')
                            
                            if df_matrix.empty:
                                st.success("Audit complete! No dashboard dependencies found for the targeted reports. You are clear.")
                            else:
                                st.warning(f"Found {len(df_matrix)} dependency link(s).")
                                
                                df_matrix['Dashboard Link'] = df_matrix['DashboardId'].apply(lambda x: f"https://{base_url}/lightning/r/Dashboard/{x}/view")
                                df_matrix['Report Link'] = df_matrix['ReportId'].apply(lambda x: f"https://{base_url}/lightning/r/Report/{x}/view")
                                
                                final_cols = df_matrix[['Dashboard Name', 'Report Name', 'Folder Name', 'Dashboard Link', 'Report Link']]
                                final_cols = final_cols.sort_values(by=['Dashboard Name', 'Report Name'])
                                
                                col_config = {
                                    "Dashboard Link": st.column_config.LinkColumn("Dashboard Action", display_text="Edit Dashboard ↗"),
                                    "Report Link": st.column_config.LinkColumn("Report Action", display_text="View Report ↗")
                                }
                                st.dataframe(final_cols, use_container_width=True, hide_index=True, column_config=col_config)
                                
                                # Add CSV Export
                                csv_zombie = final_cols.to_csv(index=False).encode('utf-8')
                                st.download_button(
                                    label="Download Matrix as CSV",
                                    data=csv_zombie,
                                    file_name="zombie_dashboards.csv",
                                    mime="text/csv",
                                    use_container_width=True
                                )
                except Exception as e:
                    st.error(f"System error during audit: {e}")

    # ==========================================
    # TAB 7: GHOST DASHBOARD SLAYER
    # ==========================================
    with tab7:
        st.subheader("👻 Ghost Dashboard Slayer")
        st.markdown("Hunt down and eradicate dashboards that are locked because their Running User was deactivated. Output the results to a CSV or mass-delete them entirely.")
        
        if st.button("Scan for Ghost Dashboards", type="primary"):
            with st.spinner("Cross-referencing dashboards against inactive user records..."):
                try:
                    # 1. Fetch Dashboards with valid running users
                    dashboards = sf.query_all("SELECT Id, Title, FolderName, RunningUserId FROM Dashboard WHERE RunningUserId != null")['records']
                    
                    # 2. Fetch inactive users
                    inactive_users = sf.query_all("SELECT Id, Name FROM User WHERE IsActive = False")['records']
                    
                    if not dashboards or not inactive_users:
                        st.success("No ghost dashboards found.")
                    else:
                        df_dash = pd.DataFrame(dashboards)
                        df_users = pd.DataFrame(inactive_users)
                        
                        df_dash = df_dash.rename(columns={'Id': 'DashboardId', 'Title': 'Dashboard Name', 'FolderName': 'Folder Name'})
                        df_users = df_users.rename(columns={'Id': 'RunningUserId', 'Name': 'Inactive User Name'})
                        
                        df_dash = df_dash.drop(columns=['attributes'], errors='ignore')
                        df_users = df_users.drop(columns=['attributes'], errors='ignore')
                        
                        # Truncate IDs to 15 characters to ensure a bulletproof merge
                        df_dash['MergeUserId'] = df_dash['RunningUserId'].str[:15]
                        df_users['MergeUserId'] = df_users['RunningUserId'].str[:15]
                        
                        ghost_matrix = pd.merge(df_dash, df_users, on='MergeUserId', how='inner')
                        
                        if ghost_matrix.empty:
                            st.success("Audit complete! No dashboards are held hostage by inactive users.")
                        else:
                            st.warning(f"Found {len(ghost_matrix)} Ghost Dashboard(s).")
                            ghost_matrix['Dashboard Link'] = ghost_matrix['DashboardId'].apply(lambda x: f"https://{base_url}/lightning/r/Dashboard/{x}/view")
                            
                            display_cols = ghost_matrix[['Dashboard Name', 'Folder Name', 'Inactive User Name', 'DashboardId', 'Dashboard Link']]
                            
                            col_config = {
                                "Dashboard Link": st.column_config.LinkColumn("Action", display_text="View Dashboard ↗")
                            }
                            st.dataframe(display_cols, use_container_width=True, hide_index=True, column_config=col_config)
                            
                            # Add CSV Export
                            csv_ghosts = display_cols.to_csv(index=False).encode('utf-8')
                            st.download_button(
                                label="Download Ghost Dashboards as CSV", 
                                data=csv_ghosts, 
                                file_name="ghost_dashboards.csv", 
                                mime="text/csv", 
                                use_container_width=True
                            )
                            
                            raw_dash_ids = ", ".join(ghost_matrix['DashboardId'].tolist())
                            st.markdown("### 📋 Copypasta Output for Deletion")
                            st.text_area("Raw Dashboard IDs:", value=raw_dash_ids, height=100)
                            
                except Exception as e:
                    st.error(f"System error during ghost audit: {e}")

        st.markdown("---")
        st.subheader("🔥 Ghost Dashboard Executioner")
        st.markdown("Paste raw Dashboard IDs below to hard delete them from the system.")
        ghost_ids_input = st.text_area("Paste Dashboard IDs to delete (comma separated):", height=100)
        
        if st.button("Execute Mass Dashboard Deletion", type="primary"):
            if ghost_ids_input:
                # Dashboard prefix is 01Z
                raw_dash_ids = re.findall(r'01Z[a-zA-Z0-9]{12,15}', ghost_ids_input) 
                unique_dash_ids = list(set(raw_dash_ids))
                
                if not unique_dash_ids:
                    st.warning("No valid Dashboard IDs found. Make sure they start with '01Z'.")
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    results = []
                    
                    for i, d_id in enumerate(unique_dash_ids):
                        status_text.text(f"Deleting {i+1} of {len(unique_dash_ids)}: {d_id}...")
                        try:
                            sf.Dashboard.delete(d_id)
                            results.append({"Dashboard ID": d_id, "Status": "✅ Deleted"})
                        except Exception as e:
                            results.append({"Dashboard ID": d_id, "Status": "❌ Failed", "Error": str(e)})
                            
                        progress_bar.progress((i + 1) / len(unique_dash_ids))
                        
                    status_text.text("Mass Deletion Complete.")
                    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
            else:
                st.warning("Please paste some IDs first.")
