"""SNS mission alerts for AWS deployments. Local mode is a no-op."""
import json
import logging
import os

ALERT_KINDS = {
    'DISPATCH', 'REROUTE', 'HOSPITAL_ETA', 'ARRIVAL', 'COMPLETE',
    'NO_ROUTE', 'ROAD_CLOSURE', 'HOSPITAL_STATUS',
}

def notify(event):
    topic = os.environ.get('ALERT_TOPIC_ARN')
    if not topic or event.get('kind') not in ALERT_KINDS:
        return False
    try:
        import boto3
        boto3.client('sns').publish(
            TopicArn=topic,
            Subject=f"RescueRoute · {event.get('kind', 'EVENT')}",
            Message=json.dumps({
                'kind': event.get('kind'),
                'text': event.get('text'),
                'mission_id': event.get('mission_id'),
                'at': event.get('at'),
                'project': 'RescueRoute Chennai',
            }, default=str),
        )
        return True
    except Exception:
        logging.exception('SNS alert publish failed')
        return False
