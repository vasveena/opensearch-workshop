import boto3
import requests
from requests_aws4auth import AWS4Auth

host = 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/' # include https:// and trailing /
region = 'us-east-1'
service = 'es'
awsauth = AWS4Auth(os.environ.get("AWS_ACCESS_KEY_ID"), os.environ.get("AWS_SECRET_ACCESS_KEY"), region, service)

# Register repository

path = '_reindex' # the OpenSearch API endpoint
url = host + path
payload={
  "source": {
    "remote": {
      "host": "https://vasveenadomain.com:443",
      "username": "admin", 
      "password": "Test123$",
      "external": True,
      "socket_timeout": "60m"
    },
    "index": "data_sentiment-6"
  },
  "dest": {
    "index": "data_sentiment_from_reindex"
  }
}

headers = {"Content-Type": "application/json"}

r = requests.post(url, auth=awsauth, json=payload, headers=headers)
print(r.status_code)
print(r.text)
