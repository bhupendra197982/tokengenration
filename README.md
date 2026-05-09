# Tradetron Token Regenerator

Automated broker token regeneration for Tradetron using GitHub Actions.

## Overview

This project automates the process of regenerating broker tokens on Tradetron without needing to use the UI manually. It runs daily at **8:30 AM IST** (Monday to Friday) via GitHub Actions.

## Features

- 🔄 Automatic token regeneration on schedule
- 🔐 Secure credential handling via GitHub Secrets
- 🕐 Runs Monday to Friday at 8:30 AM IST
- ✅ Manual trigger option available

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/bhupendra197982/tokengenration.git
cd tokengenration
```

### 2. Configure GitHub Secrets

Go to your repository **Settings → Secrets and variables → Actions** and add the following secrets:

| Secret Name | Description |
|-------------|-------------|
| `TRADETRON_EMAIL` | Your Tradetron login email |
| `TRADETRON_PASSWORD` | Your Tradetron login password |
| `TRADETRON_BROKER_ID` | Your broker ID (found in Network tab when regenerating token) |

### 3. Enable GitHub Actions

The workflow is located at `.github/workflows/schedule_tt_script.yml` and will run automatically once secrets are configured.

## Manual Execution

### Run Locally

```bash
cd backend
python3 tt_script.py
```

### Trigger via GitHub Actions

1. Go to the **Actions** tab in your repository
2. Select **Schedule tt_script.py** workflow
3. Click **Run workflow**

## Schedule

The script runs automatically at:
- **Time:** 8:30 AM IST (03:00 UTC)
- **Days:** Monday to Friday

## Project Structure

```
├── .github/
│   └── workflows/
│       └── schedule_tt_script.yml   # GitHub Actions workflow
├── backend/
│   ├── tt_script.py                 # Main token regeneration script
│   ├── kotak_client.py              # Kotak Neo API client
│   ├── main.py                      # FastAPI server
│   └── neo_api_client/              # Kotak Neo API library
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── styles.css
└── README.md
```

## How It Works

1. **Login:** Authenticates with Tradetron using email/password
2. **Solve Challenge:** Solves the Altcha proof-of-work challenge
3. **Regenerate Token:** Calls the token regeneration endpoint
4. **Verify:** Confirms successful token regeneration

## Requirements

- Python 3.11+
- `requests` library

## License

MIT License
