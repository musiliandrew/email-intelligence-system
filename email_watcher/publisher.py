import json
import os
from typing import Any
from google.cloud import pubsub_v1

class EventPublisher:
    """
    Publishes parsed email events to the CareerScope Pub/Sub Event Bus.
    """
    def __init__(self, project_id: str = None, topic_id: str = "careerscope.events"):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "careerscope-local")
        self.topic_id = topic_id
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_id)

    def publish(self, event_type: str, payload_model: Any):
        """
        Publishes the strict Pydantic payload model to the event bus.
        """
        # Convert Pydantic model to JSON bytes
        data_str = payload_model.model_dump_json()
        data = data_str.encode("utf-8")
        
        # Add attributes for routing
        future = self.publisher.publish(
            self.topic_path, 
            data, 
            event_type=event_type,
            source="email-intelligence-system"
        )
        return future.result()
