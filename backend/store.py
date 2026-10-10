"""A versioned demo-world document: SQLite transactions or DynamoDB conditional CAS."""
import copy
import json
import os
import sqlite3
import time
if __package__:
    from .data import initial_state
else:
    from data import initial_state

class Conflict(Exception):pass
class Store:
    def __init__(self,path=None,client=None,table=None):
        self.table=table or (os.environ.get('TABLE_NAME') if path is None else None)
        if self.table:
            if client is None:
                import boto3
                client=boto3.client('dynamodb')
            self.client=client
        else:
            self.path=path or os.environ.get('LOCAL_DB','rescueroute-chennai.sqlite3')
            with self.connect() as db:
                db.execute('CREATE TABLE IF NOT EXISTS world (id INTEGER PRIMARY KEY, payload TEXT)')
                db.execute('INSERT OR IGNORE INTO world VALUES (1,?)',(json.dumps(initial_state()),))

    def connect(self):return sqlite3.connect(self.path,timeout=15)
    def read(self):
        if self.table:
            response=self.client.get_item(TableName=self.table,Key={'pk':{'S':'WORLD'},'sk':{'S':'DEMO'}},ConsistentRead=True)
            return json.loads(response['Item']['payload']['S']) if 'Item' in response else initial_state()
        with self.connect() as db:return json.loads(db.execute('SELECT payload FROM world WHERE id=1').fetchone()[0])

    def mutate(self,fn):
        if not self.table:
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                state=json.loads(db.execute('SELECT payload FROM world WHERE id=1').fetchone()[0])
                result=fn(state)
                state['revision']+=1
                db.execute('UPDATE world SET payload=? WHERE id=1',(self.encode(state),))
            return state,result
        for attempt in range(6):
            state=self.read();revision=state['revision'];result=fn(state);state['revision']+=1
            condition='attribute_not_exists(revision)' if revision==0 else 'revision = :old'
            args={'TableName':self.table,'Item':{'pk':{'S':'WORLD'},'sk':{'S':'DEMO'},'revision':{'N':str(state['revision'])},'payload':{'S':self.encode(state)}},'ConditionExpression':condition}
            if revision:args['ExpressionAttributeValues']={':old':{'N':str(revision)}}
            try:
                self.client.put_item(**args)
                return state,result
            except self.client.exceptions.ConditionalCheckFailedException:
                time.sleep(.01*(attempt+1))
        raise Conflict('Another operator changed the world. Refresh and retry.')

    @staticmethod
    def encode(state):
        payload=json.dumps(state,separators=(',',':'),allow_nan=False)
        if len(payload.encode())>370000:raise Conflict('Demo state limit reached. Export history, then reset the demo.')
        return payload
