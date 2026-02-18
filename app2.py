import json
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Five9 Campaign Manager", layout="wide")


# --- Setup for PowerShell execution and installation ---
_INSTALL_DIR = Path(tempfile.gettempdir()) / "five9_installer"
_INSTALL_DIR.mkdir(exist_ok=True)
_INSTALL_STDOUT = _INSTALL_DIR / "stdout.txt"
_INSTALL_STDERR = _INSTALL_DIR / "stderr.txt"
_INSTALL_LOCK = _INSTALL_DIR / "running.lock"


def ps_base_args(command: str) -> List[str]:
    return [
        "powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", command,
    ]

def get_creation_flags() -> int:
    return subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

def ps_escape(value: str) -> str:
    return (value or "").replace("'", "''")

def run_powershell_command(username: str, password: str, command: str) -> Tuple[str, str]:
    safe_user, safe_pwd = ps_escape(username), ps_escape(password)
    ps_script = f"""
$ErrorActionPreference = 'Stop'
$secpasswd = ConvertTo-SecureString '{safe_pwd}' -AsPlainText -Force
$creds = New-Object System.Management.Automation.PSCredential ('{safe_user}', $secpasswd)
Connect-Five9AdminWebService -Credential $creds
{command}
"""
    completed = subprocess.run(
        ps_base_args(ps_script), capture_output=True, text=True, creationflags=get_creation_flags()
    )
    return completed.stdout.strip(), completed.stderr.strip()

# --- Installer and Status Functions ---
def start_install_detached(command: str):
    for f in [_INSTALL_STDOUT, _INSTALL_STDERR]:
        f.write_text("", encoding="utf-8")
    _INSTALL_LOCK.write_text("running", encoding="utf-8")
    wrapper_script = (
        f"try {{ {command} | Out-File -FilePath '{_INSTALL_STDOUT}' -Encoding utf8 }} "
        f"catch {{ $_.Exception.Message | Out-File -FilePath '{_INSTALL_STDERR}' -Encoding utf8 }}\n"
        f"finally {{ Remove-Item -Path '{_INSTALL_LOCK}' -Force -ErrorAction SilentlyContinue }}"
    )
    script_file = _INSTALL_DIR / "install_script.ps1"
    script_file.write_text(wrapper_script, encoding="utf-8")
    launch_cmd = (
        f"Start-Process powershell.exe -ArgumentList '-NoLogo','-NoProfile','-NonInteractive',"
        f"'-ExecutionPolicy','Bypass','-File','{script_file}' -WindowStyle Hidden"
    )
    subprocess.run(ps_base_args(launch_cmd), capture_output=True, text=True, creationflags=get_creation_flags())

def get_install_status() -> Dict[str, object]:
    running = _INSTALL_LOCK.exists()
    stdout = _INSTALL_STDOUT.read_text(encoding="utf-8").strip() if _INSTALL_STDOUT.exists() else ""
    stderr = _INSTALL_STDERR.read_text(encoding="utf-8").strip() if _INSTALL_STDERR.exists() else ""
    done = not running and (_INSTALL_STDOUT.exists() or _INSTALL_STDERR.exists())
    return {"running": running, "stdout": stdout, "stderr": stderr, "done": done}

# --- Data Parsing Functions ---
def parse_json_output(raw_json: str) -> List[Dict]:
    if not raw_json: return []
    try:
        parsed = json.loads(raw_json)
        return [parsed] if isinstance(parsed, dict) else parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []

def parse_campaigns_json(records: List[Dict]) -> pd.DataFrame:
    STATE_MAP = {0: "Not Running", 1: "Starting", 2: "Running", 3: "Stopping"}
    TYPE_MAP = {0: "Inbound", 1: "Outbound", 2: "AutoDial"}
    normalized = []
    for rec in records:
        lower_rec = {k.lower(): v for k, v in rec.items()}
        normalized.append({
            "Name": lower_rec.get("name", ""),
            "State": STATE_MAP.get(lower_rec.get("state"), str(lower_rec.get("state"))),
            "Type": TYPE_MAP.get(lower_rec.get("type"), str(lower_rec.get("type")))
        })
    return pd.DataFrame.from_records(normalized)

def parse_domain_lists_json(records: List[Dict]) -> pd.DataFrame:
    df = pd.DataFrame.from_records(records)
    if df.empty:
        return pd.DataFrame(columns=["name", "size"])
    return df.sort_values(by="name", ascending=True).reset_index(drop=True)

def parse_action_results(records: List[Dict]) -> Tuple[List[str], Dict[str, str]]:
    successes, failures = [], {}
    for record in records:
        name = str(record.get("Identifier", "(unknown)"))
        if record.get("Success"):
            if name not in successes: successes.append(name)
        else:
            failures[name] = str(record.get("Error") or "Unknown error")
    return successes, failures

# --- Streamlit Session State Initialization ---
def get_default_state():
    return {
        "campaigns_df": pd.DataFrame(columns=["Name", "State", "Type"]),
        "domain_lists_df": pd.DataFrame(columns=["name", "size"]),
        "list_mgmt_page": 0,
        "campaigns_with_selected_lists": [],
        "last_stdout": "", "last_stderr": "", "cached_user": "", "cached_pass": "",
    }

for key, value in get_default_state().items():
    if key not in st.session_state:
        st.session_state[key] = value

def get_effective_credentials(username, password, use_cached):
    if username and password: return username, password
    if use_cached and st.session_state.cached_user and st.session_state.cached_pass:
        return st.session_state.cached_user, st.session_state.cached_pass
    return username, password

# --- UI Sidebar ---
with st.sidebar:
    st.header("Five9 Connection")
    username = st.text_input("Five9 Username", st.session_state.cached_user)
    password = st.text_input("Five9 Password", st.session_state.cached_pass, type="password")
    use_cached = st.checkbox("Use cached credentials", value=True)
    if st.checkbox("Remember credentials for this session") and username and password:
        st.session_state.cached_user, st.session_state.cached_pass = username, password
    if st.session_state.cached_user and st.button("Clear cached credentials"):
        st.session_state.cached_user, st.session_state.cached_pass = "", ""
        st.rerun()

    st.header("PowerShell Module")
    if st.button("Install/Update Five9 Module"):
        start_install_detached("irm 'https://raw.githubusercontent.com/Five9DeveloperProgram/PSFive9Admin/main/installer.ps1' | iex")
        st.info("Install started.")

    install_status = get_install_status()
    if install_status["running"] or install_status["done"]:
        if st.button("Check Installer Status"):
            status = get_install_status()
            if status["running"]: st.info("Install running...")
            else:
                st.session_state.last_stdout, st.session_state.last_stderr = status["stdout"], status["stderr"]
                st.error("Install failed. Check Debug Console.") if status["stderr"] else st.success("Install complete.")
    
    eff_user, eff_pass = get_effective_credentials(username, password, use_cached)
    if st.button("Get Campaign Status", disabled=not (eff_user and eff_pass)):
        cmd = """
$all = @(); $types = @('Inbound', 'Outbound', 'Autodial'); 
foreach ($t in $types) { try { $all += Get-Five9Campaign -Type $t } catch {} };
$all | ForEach-Object { [pscustomobject]@{ Name = $_.name; State = $_.state.ToString(); Type = $_.type.ToString() } } | ConvertTo-Json
"""
        stdout, stderr = run_powershell_command(eff_user, eff_pass, cmd)
        st.session_state.last_stdout, st.session_state.last_stderr = stdout, stderr
        if stderr: st.error("Failed to fetch campaigns.")
        else:
            st.session_state.campaigns_df = parse_campaigns_json(parse_json_output(stdout))
            if st.session_state.campaigns_df.empty: st.warning("No campaigns returned.")

# --- Main UI ---
st.title("Five9 Campaign Manager")
tab1, tab2 = st.tabs(["Start/Stop Campaigns", "Manage Campaign Lists"])

with tab1:
    # ... (Start/Stop Campaigns tab - largely unchanged)
    st.header("Campaign State Control")
    if st.session_state.campaigns_df.empty:
        st.info("Load campaigns first using the sidebar.")
    else:
        left, right = st.columns([2, 1])
        with left:
            status_choice = st.radio("Filter by State", ["Running", "Not Running"], horizontal=True)
            running_mask = st.session_state.campaigns_df["State"].str.lower() == "running"
            filtered_df = st.session_state.campaigns_df[running_mask if status_choice == "Running" else ~running_mask]
            selected_campaigns = st.multiselect("Select Campaigns", filtered_df["Name"].tolist())
        with right:
            action_label = "Stop Selected Campaigns" if status_choice == "Running" else "Start Selected Campaigns"
            action_color = "#d33" if status_choice == "Running" else "#1f8b4c"
            confirm = st.checkbox("I confirm I want to change campaign states")
            auto_refresh = st.checkbox("Auto-refresh after action", value=True)
            action_enabled = confirm and bool(selected_campaigns) and eff_user and eff_pass
            st.markdown(f"<style>div.stButton > button:first-child {{ background-color: {action_color}; color: white; }}</style>", unsafe_allow_html=True)
            
            if st.button(action_label, disabled=not action_enabled):
                action_cmd = "Stop-Five9Campaign -Force $true" if status_choice == "Running" else "Start-Five9Campaign"
                ps_cmd = f"""
$campaigns = @({', '.join([f"'{ps_escape(c)}'" for c in selected_campaigns])});
$results = @();
foreach ($c in $campaigns) {{
    try {{ 
        {action_cmd} -Name $c;
        $results += [pscustomobject]@{{Identifier=$c; Success=$true}}
    }} catch {{
        $results += [pscustomobject]@{{Identifier=$c; Success=$false; Error=$_.Exception.Message}}
    }}
}};
$results | ConvertTo-Json -Depth 3
"""
                stdout, stderr = run_powershell_command(eff_user, eff_pass, ps_cmd)
                st.session_state.last_stdout, st.session_state.last_stderr = stdout, stderr
                if not stderr:
                    successes, failures = parse_action_results(parse_json_output(stdout))
                    if successes: st.success(f"Succeeded for: {', '.join(successes)}")
                    if failures: st.error(f"Failed for: {', '.join(failures.keys())}")
                if auto_refresh: st.rerun()

    st.header("All Campaigns")
    st.dataframe(st.session_state.campaigns_df, use_container_width=True)

with tab2:
    st.header("Manage Campaign Lists")
    if st.button("Load All Domain Lists", disabled=not (eff_user and eff_pass)):
        with st.spinner("Fetching all lists from the domain..."):
            cmd = "@(Get-Five9List) | ConvertTo-Json -Depth 3"
            stdout, stderr = run_powershell_command(eff_user, eff_pass, cmd)
            st.session_state.last_stdout, st.session_state.last_stderr = stdout, stderr
            if stderr:
                st.error("Failed to fetch domain lists.")
            else:
                st.session_state.domain_lists_df = parse_domain_lists_json(parse_json_output(stdout))
                st.session_state.list_mgmt_page = 0 # Reset page on new load

    if not st.session_state.domain_lists_df.empty:
        st.markdown("---")
        st.subheader("All Available Lists in Domain")
        
        # Pagination for Domain Lists
        page_size = 10
        df = st.session_state.domain_lists_df
        page = st.session_state.list_mgmt_page
        total_pages = int(np.ceil(len(df) / page_size))
        
        st.dataframe(df.iloc[page*page_size : (page+1)*page_size], use_container_width=True)
        
        p_col1, p_col2, p_col3 = st.columns([1, 8, 1])
        if p_col1.button("◀ Previous", disabled=(page <= 0)):
            st.session_state.list_mgmt_page -= 1
            st.rerun()
        p_col2.markdown(f"<div style='text-align: center;'>Page {page + 1} of {total_pages}</div>", unsafe_allow_html=True)
        if p_col3.button("Next ▶", disabled=(page >= total_pages - 1)):
            st.session_state.list_mgmt_page += 1
            st.rerun()

        st.markdown("---")
        action_choice = st.radio("Choose an action:", ("Add Lists to Campaigns", "Remove Lists from Campaigns"))

        if action_choice == "Add Lists to Campaigns":
            st.subheader("Add Lists")
            lists_to_add = st.multiselect("1. Select Lists to Add", df["name"].tolist())
            campaigns_to_add_to = st.multiselect("2. Select Target Campaigns", st.session_state.campaigns_df["Name"].tolist())
            
            if st.button("Execute Add Operation", disabled=not(lists_to_add and campaigns_to_add_to)):
                cmd = f"""
$lists = @({', '.join([f"'{ps_escape(l)}'" for l in lists_to_add])});
$campaigns = @({', '.join([f"'{ps_escape(c)}'" for c in campaigns_to_add_to])});
$results = @();
foreach ($c in $campaigns) {{ foreach ($l in $lists) {{
    try {{
        Add-Five9CampaignList -CampaignName $c -ListName $l;
        $results += [pscustomobject]@{{Identifier="$c -> $l"; Success=$true}}
    }} catch {{
        $results += [pscustomobject]@{{Identifier="$c -> $l"; Success=$false; Error=$_.Exception.Message}}
    }}
}} }};
$results | ConvertTo-Json -Depth 3
"""
                with st.spinner("Adding lists..."):
                    stdout, stderr = run_powershell_command(eff_user, eff_pass, cmd)
                    st.session_state.last_stdout, st.session_state.last_stderr = stdout, stderr
                    if not stderr:
                        successes, failures = parse_action_results(parse_json_output(stdout))
                        if successes: st.success(f"{len(successes)} add operations succeeded.")
                        if failures: 
                            st.error(f"{len(failures)} add operations failed. See details below.")
                            for ident, err in failures.items(): st.warning(f"- {ident}: {err}")

        elif action_choice == "Remove Lists from Campaigns":
            st.subheader("Remove Lists")
            lists_to_remove = st.multiselect("1. Select Lists to Remove", df["name"].tolist(), key="lists_to_remove_selector")

            if lists_to_remove:
                # Find campaigns that contain the selected lists
                with st.spinner("Finding campaigns containing selected lists..."):
                    find_cmd = f"""
$allCampaigns = @({', '.join([f"'{ps_escape(c)}'" for c in st.session_state.campaigns_df['Name'].tolist()])});
$listsToFind = @({', '.join([f"'{ps_escape(l)}'" for l in lists_to_remove])});
$campaignsFound = @();
foreach ($c in $allCampaigns) {{
    try {{
        $campaignLists = @(Get-Five9CampaignList -Name $c);
        $listNames = $campaignLists | Select-Object -ExpandProperty listName;
        foreach($l in $listsToFind) {{
            if ($l -in $listNames) {{
                $campaignsFound += $c;
                break;
            }}
        }}
    }} catch {{}}
}};
$campaignsFound | Select-Object -Unique | ConvertTo-Json
"""
                    stdout, stderr = run_powershell_command(eff_user, eff_pass, find_cmd)
                    if not stderr:
                        st.session_state.campaigns_with_selected_lists = parse_json_output(stdout)

                campaigns_to_remove_from = st.multiselect("2. Select Campaigns to Remove From", st.session_state.campaigns_with_selected_lists)
                
                if st.button("Execute Remove Operation", disabled=not campaigns_to_remove_from):
                    cmd = f"""
$lists = @({', '.join([f"'{ps_escape(l)}'" for l in lists_to_remove])});
$campaigns = @({', '.join([f"'{ps_escape(c)}'" for c in campaigns_to_remove_from])});
$results = @();
foreach ($c in $campaigns) {{ foreach ($l in $lists) {{
    try {{
        Remove-Five9CampaignList -CampaignName $c -ListName $l;
        $results += [pscustomobject]@{{Identifier="$c -> $l"; Success=$true}}
    }} catch {{
        $results += [pscustomobject]@{{Identifier="$c -> $l"; Success=$false; Error=$_.Exception.Message}}
    }}
}} }};
$results | ConvertTo-Json -Depth 3
"""
                    with st.spinner("Removing lists..."):
                        stdout, stderr = run_powershell_command(eff_user, eff_pass, cmd)
                        st.session_state.last_stdout, st.session_state.last_stderr = stdout, stderr
                        if not stderr:
                            successes, failures = parse_action_results(parse_json_output(stdout))
                            if successes: st.success(f"{len(successes)} remove operations succeeded.")
                            if failures: 
                                st.error(f"{len(failures)} remove operations failed. See details below.")
                                for ident, err in failures.items(): st.warning(f"- {ident}: {err}")


with st.expander("Debug Console", expanded=False):
    st.code(st.session_state.last_stdout or "(empty)", language="text")
    st.code(st.session_state.last_stderr or "(empty)", language="text")
