import os
import base64
from typing import List, Dict, Any, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

class GmailWatcherClient:
    def __init__(self, token_path: str = 'token.json', credentials_path: str = 'credentials.json'):
        self.token_path = token_path
        self.credentials_path = credentials_path
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"Missing {self.credentials_path}. Please download it from Google Cloud Console.")
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
                
        return build('gmail', 'v1', credentials=creds)

    def fetch_recent_emails(self, query: str = "subject:application OR subject:interview OR subject:update", max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Polls Gmail for recent emails matching the recruiter/application heuristic query.
        """
        results = self.service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        
        email_data_list = []
        for msg in messages:
            msg_id = msg['id']
            msg_detail = self.service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            
            headers = msg_detail['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender")
            date = next((h['value'] for h in headers if h['name'] == 'Date'), "")
            
            body = self._extract_body(msg_detail['payload'])
            
            email_data_list.append({
                "id": msg_id,
                "subject": subject,
                "sender": sender,
                "date": date,
                "body": body,
                "snippet": msg_detail.get('snippet', '')
            })
            
        return email_data_list

    def fetch_messages_by_history_id(self, history_id: str) -> List[Dict[str, Any]]:
        """
        Uses the Gmail History API to fetch only the messages that changed since history_id.
        This avoids polling and makes the Webhook highly efficient.
        """
        try:
            results = self.service.users().history().list(userId='me', startHistoryId=history_id).execute()
            histories = results.get('history', [])
            
            email_data_list = []
            for record in histories:
                # We only care about newly added messages
                messages_added = record.get('messagesAdded', [])
                for msg_added in messages_added:
                    msg = msg_added.get('message')
                    if not msg:
                        continue
                        
                    msg_id = msg['id']
                    msg_detail = self.service.users().messages().get(userId='me', id=msg_id, format='full').execute()
                    
                    headers = msg_detail['payload'].get('headers', [])
                    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
                    sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender")
                    date = next((h['value'] for h in headers if h['name'] == 'Date'), "")
                    
                    # Basic heuristic check to filter junk before passing to LLM
                    subject_lower = subject.lower()
                    if not any(k in subject_lower for k in ["application", "interview", "update", "candidate", "role", "offer"]):
                        continue
                        
                    body = self._extract_body(msg_detail['payload'])
                    
                    email_data_list.append({
                        "id": msg_id,
                        "subject": subject,
                        "sender": sender,
                        "date": date,
                        "body": body,
                        "snippet": msg_detail.get('snippet', '')
                    })
            
            return email_data_list
        except Exception as e:
            print(f"Failed to fetch history: {e}")
            return []

    def _extract_body(self, payload: Dict[str, Any]) -> str:
        """
        Recursively extracts the plain text body from the Gmail payload structure.
        """
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    return base64.urlsafe_b64decode(data).decode('utf-8')
                elif 'parts' in part:
                    return self._extract_body(part)
        elif payload.get('mimeType') == 'text/plain':
            data = payload['body'].get('data', '')
            return base64.urlsafe_b64decode(data).decode('utf-8')
            
        return ""
