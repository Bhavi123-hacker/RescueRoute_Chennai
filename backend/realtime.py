"""API Gateway WebSocket fan-out for live mission events."""
import json
import logging
import os
import time

def _table():
    name = os.environ.get('CONNECTIONS_TABLE')
    if not name:
        return None, None
    import boto3
    return boto3.resource('dynamodb').Table(name), boto3.client('apigatewaymanagementapi',
        endpoint_url=os.environ.get('WEBSOCKET_CALLBACK_URL'))

def register(connection_id):
    table, _ = _table()
    if not table or not connection_id:
        return
    table.put_item(Item={'connectionId': connection_id, 'connectedAt': int(time.time())})

def unregister(connection_id):
    table, _ = _table()
    if not table or not connection_id:
        return
    table.delete_item(Key={'connectionId': connection_id})

def broadcast(payload):
    table, client = _table()
    if not table or not client:
        return 0
    body = json.dumps(payload, default=str)
    sent = 0
    try:
        items = table.scan(ProjectionExpression='connectionId').get('Items', [])
    except Exception:
        logging.exception('WebSocket connection scan failed')
        return 0
    for item in items:
        cid = item['connectionId']
        try:
            client.post_to_connection(ConnectionId=cid, Data=body.encode())
            sent += 1
        except client.exceptions.GoneException:
            table.delete_item(Key={'connectionId': cid})
        except Exception:
            logging.exception('WebSocket post failed for %s', cid)
    return sent
