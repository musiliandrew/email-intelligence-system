import base64
import json
import logging
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

from email_watcher.gmail_client import GmailWatcherClient
from email_watcher.parser import EmailParser
from email_watcher.publisher import EventPublisher

app = FastAPI(title="CareerScope Email Intelligence System")
logger = logging.getLogger(__name__)

# Initialize components globally to reuse connections
gmail_client = None
email_parser = None
publisher = None

@app.on_event("startup")
async def startup_event():
    global gmail_client, email_parser, publisher
    try:
        gmail_client = GmailWatcherClient()
        email_parser = EmailParser()
        publisher = EventPublisher()
        logger.info("Initialized Gmail Client, Parser, and Publisher.")
    except Exception as e:
        logger.error(f"Failed to initialize components. Missing credentials? Error: {e}")

class PubSubMessage(BaseModel):
    message: dict
    subscription: str

@app.post("/webhook/gmail")
async def gmail_webhook(request: PubSubMessage):
    """
    Receives push notifications from Google Cloud Pub/Sub when a new Gmail arrives.
    """
    global gmail_client, email_parser, publisher
    
    if not gmail_client or not email_parser or not publisher:
        raise HTTPException(status_code=503, detail="System not fully initialized.")

    # 1. Extract data from the Pub/Sub push notification
    try:
        pubsub_message = request.message
        data = base64.b64decode(pubsub_message.get("data", "")).decode("utf-8")
        payload = json.loads(data)
        
        email_address = payload.get("emailAddress")
        history_id = payload.get("historyId")
        
        logger.info(f"Received webhook for {email_address} with historyId: {history_id}")
    except Exception as e:
        logger.error(f"Failed to decode Pub/Sub message: {e}")
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub payload")

    # 2. Fetch the specific new messages using the historyId
    try:
        new_emails = gmail_client.fetch_messages_by_history_id(history_id)
        if not new_emails:
            return {"status": "ok", "message": "No relevant emails found in this history segment."}
            
    except Exception as e:
        logger.error(f"Error fetching emails from Gmail API: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch emails")

    # 3. Parse each email and publish events
    processed_count = 0
    for email_data in new_emails:
        try:
            parsed_event = await email_parser.parse(email_data, user_id=1) # Mock user_id 1 for now
            if parsed_event:
                event_type = parsed_event.__class__.__name__
                publisher.publish(event_type=event_type, payload_model=parsed_event)
                logger.info(f"Published {event_type} for {parsed_event.company_name}")
                processed_count += 1
        except Exception as e:
            logger.error(f"Failed to parse or publish email {email_data.get('id')}: {e}")

    return {"status": "ok", "processed_events": processed_count}

@app.post("/webhook/agent/followup")
async def trigger_followup_agent(request: Request):
    """
    Triggered by the Event Bus when 7 days have passed since an application.
    Executes the Follow-up Agent to generate and save a draft in Gmail.
    """
    from agents.followup_agent import FollowUpAgent
    
    body = await request.json()
    company_name = body.get("company_name")
    role_title = body.get("role_title")
    recruiter_email = body.get("recruiter_email")
    
    if not company_name or not role_title or not recruiter_email:
        raise HTTPException(status_code=400, detail="Missing required fields")
        
    agent = FollowUpAgent()
    draft_id = await agent.execute(company_name, role_title, recruiter_email)
    
    if draft_id:
        return {"status": "ok", "draft_id": draft_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to execute Follow-up Agent")
