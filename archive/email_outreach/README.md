Email Outreach – Speaker Registration

This utility generates a messages.json file from the speakers CSV and a template, suitable for driving a Gmail/Google OAuth sender or similar tool.

Input CSV
- Expected headers: `Speakers`, `Confirmed`, `Email`
- Multiple emails in the `Email` field are supported (comma/semicolon separated)

Default Template Placeholders
- `{{speaker_name}}`
- `{{form_url}}` (defaults to the Jotform link)
- `{{ticket_code}}` (defaults to `speaker2025`)

Quick Start (Windows PowerShell)
```powershell
python .\email_outreach\generate_messages.py -i "Conference Speaker Schedule 2025 - Sheet28.csv" -o .\email_outreach\messages.json --send-to-all-on-row --preview-csv .\email_outreach\preview.csv
```

Options
- `--subject` to change the subject
- `--cc` to override CC list (defaults: serdar@mobidictum.com batuhan@mobidictum.com)
- `--form-url` and `--ticket-code` to adjust link/code
- `--include-unconfirmed` to include non-"Yes" rows
- `--limit N` to preview N messages only
- `--exclude-file path.txt` to skip emails listed (one per line)

Output JSON schema (per message)
```json
{
  "to": ["to@example.com"],
  "cc": ["serdar@mobidictum.com", "batuhan@mobidictum.com"],
  "subject": "Action Required: Speaker Registration – Mobidictum Conference 2025",
  "text": "Plain text body",
  "html": "<p>HTML body</p>",
  "metadata": { "speaker_name": "Full Name", "confirmed": "Yes" }
}
```

Notes
- Unicode is preserved in both text and HTML.
- The HTML body is a simple conversion from the text body with linkified URLs and line breaks.

Test a single message
```powershell
python .\email_outreach\generate_test_message.py --to "serdar@mobidictum.com" --cc "contact@serdarakman.com" --name "Serdar"
```

Send via Gmail (OAuth)
1) Install dependencies
```powershell
pip install -r .\email_outreach\requirements.txt
```
2) First-time auth will open a browser; ensure you use the correct Google account.
3) Dry run (no send):
```powershell
python .\email_outreach\send_gmail.py --input .\email_outreach\test_message.json --credentials .\client_secret_31032819643-uuaepmbvqtnku3pvlup2njqpuiikd97k.apps.googleusercontent.com.json --dry-run
```
4) Send the test message:
```powershell
python .\email_outreach\send_gmail.py --input .\email_outreach\test_message.json --credentials .\client_secret_31032819643-uuaepmbvqtnku3pvlup2njqpuiikd97k.apps.googleusercontent.com.json --from-address "Mobidictum Conference <serdar@mobidictum.com>"
```
5) Send all (rate-limited):
```powershell
python .\email_outreach\send_gmail.py --input .\email_outreach\messages.json --credentials .\client_secret_31032819643-uuaepmbvqtnku3pvlup2njqpuiikd97k.apps.googleusercontent.com.json --from-address "Mobidictum Conference <serdar@mobidictum.com>" --delay 5
```


