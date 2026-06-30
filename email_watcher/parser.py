import asyncio
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field

# We will use the shared AI Executor we built in Phase 1
from shared.config.decision import DecisionSettings
from shared.ai.executor import AIExecutor
from shared.contracts.events.application_events import (
    ApplicationReceivedPayload,
    InterviewInvitedPayload,
    ApplicationRejectedPayload
)

class ParsedEmailResult(BaseModel):
    event_type: str = Field(..., description="ApplicationReceived, InterviewInvited, ApplicationRejected, or Unknown")
    company_name: str = Field(..., description="Company name")
    role_title: str = Field(..., description="Job role title")
    # For Interviews
    interview_date: Optional[str] = None
    recruiter_name: Optional[str] = None
    # For Rejections
    missing_skills: list[str] = Field(default_factory=list)
    extracted_feedback: Optional[str] = None

class EmailParser:
    def __init__(self, settings: Optional[DecisionSettings] = None):
        if not settings:
            settings = DecisionSettings()
        self.executor = AIExecutor(settings)

    async def parse(self, email_data: Dict[str, Any], user_id: int) -> Optional[Union[ApplicationReceivedPayload, InterviewInvitedPayload, ApplicationRejectedPayload]]:
        variables = {
            "email_subject": email_data.get("subject", ""),
            "email_sender": email_data.get("sender", ""),
            "email_body": email_data.get("body", "")
        }
        
        result: ParsedEmailResult = await self.executor.execute(
            prompt_name="email.parse_email",
            response_model=ParsedEmailResult,
            variables=variables
        )
        
        if result.event_type == "Unknown":
            return None
            
        snippet = email_data.get("snippet", "")
        msg_id = email_data.get("id", "")
        date = email_data.get("date", "")
        # Parse standard date string into datetime if possible, but for mock, let's keep it simple
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        
        if result.event_type == "ApplicationReceived":
            return ApplicationReceivedPayload(
                user_id=user_id,
                company_name=result.company_name,
                role_title=result.role_title,
                applied_at=now,
                source_email_id=msg_id,
                raw_email_snippet=snippet
            )
        elif result.event_type == "InterviewInvited":
            return InterviewInvitedPayload(
                user_id=user_id,
                company_name=result.company_name,
                role_title=result.role_title,
                interview_date=None, # Could parse result.interview_date
                recruiter_name=result.recruiter_name,
                source_email_id=msg_id,
                raw_email_snippet=snippet
            )
        elif result.event_type == "ApplicationRejected":
            return ApplicationRejectedPayload(
                user_id=user_id,
                company_name=result.company_name,
                role_title=result.role_title,
                rejected_at=now,
                extracted_feedback=result.extracted_feedback,
                missing_skills=result.missing_skills,
                source_email_id=msg_id,
                raw_email_snippet=snippet
            )
            
        return None
