# Five9 Admin Manager App

A Windows Streamlit application for managing Five9 VCC campaigns and campaign contact lists through the PSFive9Admin PowerShell module.

## What this app does

### Tab 1 - Start/Stop Campaigns
- Connects to Five9 Admin Web Service using your credentials.
- Retrieves campaign status for Inbound, Outbound, and AutoDial campaigns.
- Lets you filter campaigns by running state.
- Starts or stops selected campaigns with confirmation control.

### Tab 2 - Manage Campaign Lists
- Browses all domain contact lists (paginated, 10 per page).
- Adds contact lists to one or more campaigns in batch.
- Removes contact lists from campaigns (auto-discovers which campaigns contain them).

### Other
- Install/update PSFive9Admin PowerShell module from the sidebar.
- Cache credentials for the session.
- Debug Console for troubleshooting PowerShell output.

## Repository contents
- `app2.py` - Python Streamlit app source (current version).
- `app.py` - Original app source (campaign start/stop only).
- `requirements.txt` - Python dependencies for source execution.
- `Five9CampaignManager_Lean.exe` - Prebuilt Windows executable (based on app.py).
- `docs/` - Documentation folder.

## Prerequisites
### Hardware
- 2 CPU cores minimum (4 recommended)
- 4 GB RAM minimum (8 GB recommended)
- 500 MB free disk space

### Software
- Windows 10/11 (64-bit) or Windows Server 2019/2022
- Windows PowerShell 5.1 (powershell.exe available)
- Modern browser (Edge, Chrome, Firefox)

### Network access
- Outbound HTTPS to raw.githubusercontent.com (for module installer)
- Outbound HTTPS to Five9 admin/service endpoints
- Localhost access to 127.0.0.1 for app UI

## Option A: Run the executable (v1 only)
1. Download `Five9CampaignManager_Lean.exe`.
2. Double-click the EXE.
3. Allow SmartScreen/Defender prompt if it appears.
4. Your browser opens automatically to the local app page.
5. In the sidebar:
   - Enter Five9 username and password.
   - Click **Install/Update Five9 Module** (first run or when needed).
   - Click **Check Installer Status** until installation finishes.
   - Click **Get Campaign Status**.
6. Select campaigns and execute Start/Stop actions.

## Option B: Run from source (recommended for app2.py)
1. Install Python 3.8+.
2. In a terminal, open the project folder.
3. Install dependencies:
   `pip install -r requirements.txt`
4. Start app:
   `streamlit run app2.py`
5. Open the shown localhost URL in your browser.

## How to use the app
1. Provide Five9 credentials in sidebar.
2. (Optional) Enable credential caching for current session.
3. Fetch campaigns with **Get Campaign Status**.

### Start/Stop Campaigns (Tab 1)
4. Choose filter: **Running** or **Not Running**.
5. Select one or more campaigns.
6. Check **I confirm I want to change campaign states**.
7. Click the action button (**Stop** or **Start**).
8. Review success/failure feedback.

### Manage Campaign Lists (Tab 2)
4. Click **Load All Domain Lists** to browse lists.
5. Choose **Add Lists to Campaigns** or **Remove Lists from Campaigns**.
6. For adding: select lists and target campaigns, then click **Execute Add Operation**.
7. For removing: select lists, wait for auto-discovery of campaigns containing them, select campaigns, then click **Execute Remove Operation**.

## Documentation
- `docs/01_How_The_Code_Works.md` - Architecture and code walkthrough for the original app.
- `docs/02_Why_Previous_Versions_Failed.md` - History of debugging iterations.
- `docs/03_App2_How_It_Works.md` - Detailed documentation for app2.py.

## Security notes
- Credentials are used to create a PowerShell PSCredential and connect to Five9.
- Session-cached credentials are in memory for the running app session.
- Avoid sharing screenshots/logs that expose usernames or errors containing sensitive details.

## Troubleshooting
### Module install seems stuck
- Click **Check Installer Status**.
- If needed, retry the install.

### No campaigns returned
- Confirm credentials are valid.
- Confirm Five9 user has permission to view campaigns.
- Check Debug Console for stdout and stderr.

### EXE blocked by security tools
- Use SmartScreen **Run anyway** if policy allows.
- Ask IT to allowlist the executable if required.

### Cannot connect to Five9
- Verify corporate network/firewall allows outbound access to Five9 endpoints.
- Confirm VPN/proxy settings.

## Known constraints
- This app is Windows-oriented due to powershell.exe and PSFive9Admin dependency.
- Streamlit Community Cloud and Linux-native hosting require refactor away from PowerShell module usage.