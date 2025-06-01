import functions_framework
from cloudevents.http import CloudEvent
from inference.pipeline import run
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@functions_framework.cloud_event
def scheduled_pipeline(event: CloudEvent) -> None:
    """Triggered from Pub/Sub via Cloud Scheduler."""
    print("Pub/Sub message received, running pipeline…")
    run()
