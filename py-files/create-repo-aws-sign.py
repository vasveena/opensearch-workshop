import os
import boto3
import requests
from requests_aws4auth import AWS4Auth

host = 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/' # include https:// and trailing /
region = 'us-east-1'
service = 'es'
awsauth = AWS4Auth(os.environ.get("AWS_ACCESS_KEY_ID"), os.environ.get("AWS_SECRET_ACCESS_KEY"), region, service)

# Register repository

path = '_snapshot/s3-repository' # the OpenSearch API endpoint
url = host + path

payload = {
  "type": "s3",
  "settings": {
    "bucket": "oss-es-snapshots",
    "region": "us-east-1",
    "role_arn": "arn:aws:iam::413094830157:role/opensearch-s3-role"
  }
}

headers = {"Content-Type": "application/json"}

r = requests.put(url, auth=awsauth, json=payload, headers=headers)

print(r.status_code)
print(r.text)
