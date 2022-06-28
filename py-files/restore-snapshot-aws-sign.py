# Restore from S3 snapshot

import os
import boto3
import requests
from requests_aws4auth import AWS4Auth

host = 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/' # include https:// and trailing /
region = 'us-east-1'
service = 'es'
awsauth = AWS4Auth(os.environ.get("AWS_ACCESS_KEY_ID"), os.environ.get("AWS_SECRET_ACCESS_KEY"), region, service)

# Restore specific snapshot

path = '_snapshot/s3-repository/snapshot_2/_restore'
url = host + path

payload = {
   "indices": "data_sentiment-6",
   "include_global_state": False
 }

headers = {"Content-Type": "application/json"}

r = requests.post(url, auth=awsauth, json=payload, headers=headers)
print(r.text)
