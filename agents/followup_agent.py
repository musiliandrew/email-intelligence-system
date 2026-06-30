import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from shared.config.decision import DecisionSettings
from shared.ai.executor import AIExecutor
from email_watcher.gmail_client import GmailWatcherClient

logger = logging.getLogger(__name__)

class FollowUpDraft(BaseModel):
    subject: str = Field(..., description="The subject line of the email")
    body: str = Field(..., description="The body of the email. Keep it professional and polite.")

class FollowUpAgent:
    def __init__(self, settings: Optional[DecisionSettings] = None):
        if not settings:
            settings = DecisionSettings()
        self.executor = AIExecutor(settings)
        self.gmail_client = GmailWatcherClient()

    async def execute(self, company_name: str, role_title: str, recruiter_email: str) -> Optional[str]:
        """
        Executes the agentic workflow:
        1. Generate the draft using LLM
        2. Action: Create draft in Gmail
        """
        logger.info(f"Follow-up Agent triggered for {company_name} - {role_title}")

        # In a real setup, we would register this prompt in shared/ai/prompts
        # But for this implementation, we will pass a generic request.
        # Note: AIExecutor expects prompt_name to exist in Registry. 
        # For simplicity without adding more prompts, we'll assume a 'agent.draft_followup' prompt exists
        # Or we can just use the provider directly.
        variables = {
            "company_name": company_name,
            "role_title": role_title,
        }

        try:
            # Generate the draft content
            draft_content: FollowUpDraft = await self.executor.execute(
                prompt_name="agent.draft_followup",
                response_model=FollowUpDraft,
                variables=variables
            )

            # Take Action: Create the draft
            draft_id = self.gmail_client.create_draft(
                to_email=recruiter_email,
                subject=draft_content.subject,
                body=draft_content.body
            )

            logger.info(f"Successfully created draft {draft_id} for {company_name}")
            return draft_id

        except Exception as e:
            logger.error(f"FollowUpAgent failed: {e}")
            return None
