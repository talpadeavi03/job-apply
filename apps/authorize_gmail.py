"""One-time local Gmail OAuth authorization script."""
import json
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CLIENT_FILE = Path("credentials.json")
ENV_FILE = Path(".env")


def main() -> None:
    if not CLIENT_FILE.exists():
        raise SystemExit(
            "Missing credentials.json. Please ensure your Google Cloud OAuth Client JSON is saved as 'credentials.json'."
        )

    print("Initiating Gmail OAuth Flow...")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    payload = json.loads(creds.to_json())

    client_id = payload.get("client_id", "")
    client_secret = payload.get("client_secret", "")
    refresh_token = payload.get("refresh_token", "")

    # Append / update in local .env
    env_lines = []
    if ENV_FILE.exists():
        env_lines = [
            line for line in ENV_FILE.read_text(encoding="utf-8").splitlines()
            if not any(line.startswith(k) for k in ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"])
        ]

    env_lines.append(f"GMAIL_CLIENT_ID={client_id}")
    env_lines.append(f"GMAIL_CLIENT_SECRET={client_secret}")
    env_lines.append(f"GMAIL_REFRESH_TOKEN={refresh_token}")

    ENV_FILE.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    print("\n[SUCCESS] Gmail tokens saved to local .env file!")
    print("\nFor GitHub Actions (cloud runner), add these to GitHub Secrets:")
    print(f"- GMAIL_CLIENT_ID: {client_id}")
    print("- GMAIL_CLIENT_SECRET: [Saved to .env]")
    print("- GMAIL_REFRESH_TOKEN: [Saved to .env]")


if __name__ == "__main__":
    main()
