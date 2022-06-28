**OSS Elasticsearch 5.6 to Amazon Opensearch 1.2**
**//////////////////////////////////////////////////////**

**Upgrade from OSS ES 5.6 to OSS ES 6.8 (min version required to migrate to Amazon OS)**

*Step 1 - Take a snapshot of your OSS Elasticsearch cluster*
*------------------------------------------------------------*

1. Taking snapshot is required even if you are not using this as the primary approach to back up your data. We cannot roll back to an earlier version without a snapshot. Snapshot is the image of the entire cluster state at a given point in time. i.e.,  cluster settings, nodes settings and index metadata. Not only are snapshots useful for recovery from a failure, but also for migrations.

```
# Install S3 repo on all ES nodes

/home/ec2-user/elasticsearch-5.6.16/bin/elasticsearch-plugin install repository-s3

# Create Keystore to save your access/secret key of s3 on ALL ES nodes
# Get STS creds from Isengard or create user and specify credentials

/home/ec2-user/elasticsearch-5.6.16/bin/elasticsearch-keystore create
/home/ec2-user/elasticsearch-5.6.16/bin/elasticsearch-keystore add s3.client.default.access_key
/home/ec2-user/elasticsearch-5.6.16/bin/elasticsearch-keystore add s3.client.default.secret_key

# Re-start elasticsearch on all ES nodes
pkill -f elasticsearch
/home/ec2-user/elasticsearch-5.6.16/bin/elasticsearch > ~/elastic.out 2>&1 &

# Following command returns empty
curl -XGET http://ip-80-0-18-136.ec2.internal:9200/_snapshot/_all
{}

# Create snapshot in S3

curl -XPUT http://ip-80-0-18-136.ec2.internal:9200/_snapshot/s3_backup -d'
{
  "type": "s3",
  "settings": {
    "bucket": "oss-es-snapshots"
  }
}'
'

# Verify that snapshot is created

curl -XGET http://ip-80-0-18-136.ec2.internal:9200/_snapshot/_all

# Start your snapshot

curl -X PUT "ip-80-0-18-136.ec2.internal:9200/_snapshot/s3_backup/snapshot_1?wait_for_completion=false"

# Check snapshot status
curl -X GET "ip-80-0-18-136.ec2.internal:9200/_snapshot/s3_backup/snapshot_1"

```

2. Perform rolling upgrade from 5.6 to 6.8

```
curl -X PUT http://ip-80-0-18-136.ec2.internal:9200/_cluster/settings -d '
{
  "persistent": {
    "cluster.routing.allocation.enable": "primaries"
  }
}'

```

*Step 2 - Perform Rolling Upgrades from 5.x to 6.x*
*-----------------------------------------------------*

Rolling upgrade involves upgrading ES version one node at a time and re-starting. Please note that if you do not want any downtime, you need to make sure that number of mandated masters is less than total number of masters - 1.

1. Disable shard allocation to avoid high IO cost during shard replication from node currently undergoing rolling upgrade to other nodes in the cluster.

```
curl -X PUT http://ip-80-0-18-136.ec2.internal:9200/_cluster/settings -d '
{
  "persistent": {
    "cluster.routing.allocation.enable": "primaries"
  }
}'
```

2. Stop non-essential indexing and perform a synced flush (optional). While you can continue indexing during the upgrade, shard recovery is much faster if you temporarily stop non-essential indexing.

```
curl -X POST http://ip-80-0-18-136.ec2.internal:9200/_flush/synced
```

3. Run the following commands on ALL the OSS Elasticsearch nodes - one by one. DO NOT run these commands on more than one node simultaneously.

# Download latest minor version from OSS Elasticsearch 6.8.x and verify checksum

```
wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-oss-6.8.23.tar.gz
wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-oss-6.8.23.tar.gz.sha512

shasum -a 512 -c elasticsearch-oss-6.8.23.tar.gz.sha512

# Extract TAR

tar -xzf elasticsearch-oss-6.8.23.tar.gz
cd elasticsearch-6.8.23
echo 'export ES_HOME=/home/ec2-user/elasticsearch-6.8.23/' >> ~/.bashrc
source ~/.bashrc

# Update the new ES_HOME settings YAML file.
# IMPORTANT - Change the node.name value for every node.
# For last node, set node.master to false

echo "cluster.name: oss-es-cluster" >> $ES_HOME/config/elasticsearch.yml
echo "node.name: node-1" >> $ES_HOME/config/elasticsearch.yml
echo "node.master: true" >> $ES_HOME/config/elasticsearch.yml
echo "node.data: true" >> $ES_HOME/config/elasticsearch.yml
echo "path.data: /mnt/elasticsearch/data/" >> $ES_HOME/config/elasticsearch.yml
echo "path.logs: /mnt/elasticsearch/logs/" >> $ES_HOME/config/elasticsearch.yml
echo "discovery.zen.minimum_master_nodes: 3" >> $ES_HOME/config/elasticsearch.yml
echo "discovery.zen.ping.unicast.hosts: [\"80.0.18.136:9300\", \"80.0.29.251:9300\",\"80.0.30.161:9300\",\"80.0.28.34:9300\"]" >> $ES_HOME/config/elasticsearch.yml
echo "network.bind_host: 0.0.0.0" >> $ES_HOME/config/elasticsearch.yml
echo "network.publish_host: $(hostname -f)" >> $ES_HOME/config/elasticsearch.yml
echo "transport.tcp.port: 9300" >> $ES_HOME/config/elasticsearch.yml
echo "transport.host: $(hostname -I | awk '{print $1}')" >> $ES_HOME/config/elasticsearch.yml

# Get current version before proceeding with upgrade

curl -X GET "http://ip-80-0-18-136.ec2.internal:9200?pretty"

# Stop current ES process
pkill -f elasticsearch

# Start new ES process
$ES_HOME/bin/elasticsearch > ~/elastic-6.out 2>&1 &

# Check if the new node joined the cluster
curl -XGET 'ip-80-0-18-136.ec2.internal:9200/_nodes/_all'
```

4. Once you have done the above steps for ALL the nodes, make sure the cluster version is changed to 6.8.23

```
curl -X GET "http://ip-80-0-18-136.ec2.internal:9200?pretty"
{
  "name" : "node-1",
  "cluster_name" : "oss-es-cluster",
  "cluster_uuid" : "WTy25XCjROiNjCtS0InhwQ",
  "version" : {
    "number" : "6.8.23",
    "build_flavor" : "oss",
    "build_type" : "tar",
    "build_hash" : "4f67856",
    "build_date" : "2022-01-06T21:30:50.087716Z",
    "build_snapshot" : false,
    "lucene_version" : "7.7.3",
    "minimum_wire_compatibility_version" : "5.6.0",
    "minimum_index_compatibility_version" : "5.0.0"
  },
  "tagline" : "You Know, for Search"
}
```

5. Re-enable shard allocation and verify health

```
curl -X PUT http://ip-80-0-18-136.ec2.internal:9200/_cluster/settings -H 'Content-Type: application/json' -d '
{
  "persistent": {
    "cluster.routing.allocation.enable": null
  }
}'

curl -X GET http://ip-80-0-18-136.ec2.internal:9200/_cat/recovery

```

6. Install and upgrade s3 plugin and restart elasticsearch on all nodes. This step needs to be for every plugin. In our case, we only used S3 plugin.

```
# Install S3 repo on all ES nodes

$ES_HOME/bin/elasticsearch-plugin install repository-s3

# Create Keystore to save your access/secret key of s3 on ALL ES nodes
# Get STS creds from Isengard or create user and specify credentials

$ES_HOME/bin/elasticsearch-keystore create
$ES_HOME/bin/elasticsearch-keystore add s3.client.default.access_key
$ES_HOME/bin/elasticsearch-keystore add s3.client.default.secret_key
```

*Step 3 - Re-index documents*
*----------------------------*

Since we moved from 5.x to 6.x, we need to re-index the documents. The clients will work fine without this step but it may cause some compatibility issues down the line. For instance, datatype “string” has to be changed to “text”. This step will take a while to complete based on the index size.

```
# Create new index
curl -X PUT "localhost:9200/data_sentiment-6" -H 'Content-Type: application/json' -d '
{
          "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 2
          },
          "mappings" : {
          "_default_" : {
           "properties" : {
             "user" : {"type": "text"},
             "timestamp" : { "type" : "date", "format" :  "yyyy-MM-dd HH:mm:ss"},
             "tweet" : {"type": "text"},
             "polarity" : {"type" : "double"},
             "subjectivity" : {"type" : "double"},
             "sentiment" : {"type": "text"}
            }
           }
          }
         }
       '

# Re-index

curl -X POST "localhost:9200/_reindex" -H 'Content-Type: application/json' -d '
{
   "source":{
      "index":"data_sentiment"
   },
   "dest":{
      "index":"data_sentiment-6"
   }
}'

# Remove old index and create alias for new index

curl -X POST "localhost:9200/_aliases" -H 'Content-Type: application/json' -d'
{
"actions" : [
{ "add": { "index": "data_sentiment-6", "alias": "data_sentiment" } },
{ "remove_index": { "index": "data_sentiment" } }
]
}'

```

*Step 4 - Test Client program (Optional)*
*----------------------------------------*

Run client twitter API program and verify that there are no errors or see if the count is getting increased

```
curl -X GET "localhost:9200/data_sentiment-6/_count"
```

**Migrate from OSS Elasticsearch 6.8 to Opensearch 1.2**
**-----------------------------------------------------**

*Step 5 - Create OpenSearch cluster*
*----------------------------------------*

In Amazon OpenSearch Management Console, create your Amazon OpenSearch 1.2 domain within a VPC. I used master user with password to make it easy. But it is very much recommended to use IAM credentials with SAML or AWS Cognito or FGAC. Please refer to this documentation (https://docs.aws.amazon.com/opensearch-service/latest/developerguide/dashboards.html) for more details.

Using local port forwarding, check if you are able to access your domain. For this, you need to create an EC2 instance in a public subnet with same network settings. Or use the ES client instance created earlier.

```
ssh -i ~/awspsaeast.pem ec2-user@ec2-3-83-111-79.compute-1.amazonaws.com -N -L 9200:vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443
```

Access the cluster and dashboards in browser.

https://localhost:9200
https://localhost:9200/_dashboards

# Test using cURL from local desktop
```
curl -XPUT -u 'admin:Test123$' 'https://localhost:9200/movies/_doc/1' -d '{"director": "Burton, Tim", "genre": ["Comedy","Sci-Fi"], "year": 1996, "actor": ["Jack Nicholson","Pierce Brosnan","Sarah Jessica Parker"], "title": "Mars Attacks!"}' -H 'Content-Type: application/json' --cacert localhost.crt -k

 # Test using cURL from EC2 client
 curl -XPUT -u 'admin:Test123$' 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/movies/_doc/1' -d '{"director": "Burton, Tim", "genre": ["Comedy","Sci-Fi"], "year": 1996, "actor": ["Jack Nicholson","Pierce Brosnan","Sarah Jessica Parker"], "title": "Mars Attacks!"}' -H 'Content-Type: application/json' -k
```

*Step 6 - Take a snapshot of source index*
*----------------------------------------*

First step is to take snapshot of the source OSS cluster. This time, we will change the snapshot name to snapshot_2.

```
# Verify that S3 snapshot exists. If not, create it.

curl -XGET http://ip-80-0-18-136.ec2.internal:9200/_snapshot/_all

# Start your snapshot with a different snapshot ID (snapshot_2)

curl -X PUT "ip-80-0-18-136.ec2.internal:9200/_snapshot/s3_backup/snapshot_2?wait_for_completion=false"

# Check snapshot status
curl -X GET "ip-80-0-18-136.ec2.internal:9200/_snapshot/s3_backup/snapshot_2"

```

You can restore snapshot directly from S3 using _restore API. But it will be a point-in-time snapshot.

*Step 7 - Configure role mapping for manual snapshot*
*-----------------------------------------------------*

1. Create an IAM role “opensearch-s3-role” with permissions to the S3 location where we stored the snapshot
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
                "s3:ListBucket"
            ],
            "Effect": "Allow",
            "Resource": [
                "arn:aws:s3:::oss-es-snapshots"
            ]
        },
        {
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Effect": "Allow",
            "Resource": [
                "arn:aws:s3:::oss-es-snapshots/*"
            ]
        }
    ]
}
```

Modify the trust policy for this role to trust OpenSearch service.
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "",
            "Effect": "Allow",
            "Principal": {
                "Service": "opensearchservice.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}

```

2. Create a role “opensearch-superuser” and provide following permissions. We will use this user’s credentials to sign requests for using snapshot API.

```
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::413094830157:role/opensearch-s3-role"
    },
    {
      "Effect": "Allow",
      "Action": "es:ESHttpPut",
      "Resource": "arn:aws:es:region:413094830157:domain/opensearch-domain-2/*"
    }
  ]
}
```

3. Go to Opensearch dashboards → Security → Roles → search for “manage_snapshots” → select manage_snapshots → Mapped Users. Add the user’s ARN.

*Important: For any snapshot operation in Amazon Opensearch we need to sign all our snapshot requests using SDK or Rest API*

We will use boto3 client to create S3 index. You cannot use cURL or even the dashboard here because Amazon OpenSearch requires you to sign your request. You can use any AWS SDK or rest API like Postman that allows AWS signature.

If we do not sign our requests, we will get the below error.

```
curl -XPOST -u 'admin:Test123$' 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/_snapshot/s3-repository/snapshot-2/_restore'
{"error":{"root_cause":[{"type":"security_exception","reason":"no permissions for [] and User [name=admin, backend_roles=[], requestedTenant=null]"}],"type":"security_exception","reason":"no permissions for [] and User [name=admin, backend_roles=[], requestedTenant=null]"},"status":403}
```

*Step 8 - Create an S3 repository in Opensearch cluster*
*-----------------------------------------------------*

Login to the ES client and install required packages.

```
pip3 install boto3
pip3 install requests_aws4auth
```

Use boto3 client to create S3 index. AWS Access Key and Secret Keys are of the user “opensearch-superuser” to whom we provided the role mapping in previous step. Using it directly within the script is bad practice. Please recommend exporting them or using AWS Secret Agent.

```
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

```

It should return 200 OK. You should be able to see the snapshot we took from OSS cluster since both domains refer to the same S3 bucket.

curl -XGET -u 'admin:Test123$' 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/_snapshot/s3-repository/snapshot_2/'

*Step 9 - Restore from snapshot*
*--------------------------------*

Now let’s restore the index “data_sentiment”. We cannot restore other indexes because we did not reindex them from OSS Elasticsearch 5.6.16 to 6.8. However, you can restore all indexes at the same time if you re-indexed all of them to 6.8.

```
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

```

*Step 10 - Validate Restoration*
*--------------------------------*

Verify the count of documents between source and destination

curl -X GET 'ip-80-0-18-136.ec2.internal:9200/data_sentiment-6/_count' -k
curl -X GET -u 'admin:Test123$' 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/data_sentiment-6/_count' -k

sar -n DEV 1 3

https://aws.amazon.com/blogs/big-data/ingest-streaming-data-into-amazon-elasticsearch-service-within-the-privacy-of-your-vpc-with-amazon-kinesis-data-firehose/

*Final Step - Upgrade Clients*
*--------------------------------*

Writer -> OSS ES -> (sync) Firehose -> (async) Opensearch

```
import os
import json
import boto3
import tweepy
import pytz
from tweepy import OAuthHandler
from tweepy import StreamingClient
from textblob import TextBlob
from elasticsearch import Elasticsearch, RequestsHttpConnection
from datetime import datetime
import requests
from requests_aws4auth import AWS4Auth

class process_tweet(tweepy.StreamingClient):
  print("in process_tweet")
  def on_data(self, data):
    print("on_data")
    # decode json
    dict_data = json.loads(data)

    # pass tweet into TextBlob
    tweet_id = TextBlob(dict_data['data']['id'])
    timestamp = datetime.now().astimezone(est).strftime("%Y-%m-%d %H:%M:%S")
    tweet = TextBlob(dict_data['data']['text'])
    tweetstr = str(tweet)
    user_name = tweetstr[tweetstr.find('@')+1 : tweetstr.find(':')]

    # determine if sentiment is positive, negative, or neutral
    if tweet.sentiment.polarity < 0:
        sentiment = "negative"
    elif tweet.sentiment.polarity == 0:
        sentiment = "neutral"
    else:
        sentiment = "positive"

    # output values
    print("tweet_id: "+ str(tweet_id))
    print("timestamp: " +timestamp)
    print("user_name: " + user_name)
    print("tweet_polarity: " + str(tweet.sentiment.polarity))
    print("tweet_subjectivity: " + str(tweet.sentiment.subjectivity))
    print("sentiment: " + sentiment)

    final_data = {}
    final_data['tweet_id'] = str(tweet_id)
    final_data['timestamp'] = timestamp
    final_data['user_name'] = user_name
    final_data['tweet_polarity'] = str(tweet.sentiment.polarity)
    final_data['tweet_subjectivity'] = str(tweet.sentiment.subjectivity)
    final_data['sentiment'] = sentiment

    json_data = json.dumps(final_data)

    # index values into OSS Elasticsearch
    es.index(index="data_sentiment",
                 doc_type="test-type",
                 body=json_data)

    # Write to Kinesis Firehose with delivery stream set to Amazon OpenSearch
    fh.put_record(
            DeliveryStreamName='PUT-OPS-4WTZi',
            Record={'Data': json_data},
        )

  def on_error(self, status):
    print(status)

if __name__ == '__main__':
#def handler(event, context):
    print("in handler")

    # Create client instance for elasticsearch
    print("create client instance for elasticsearch")

    # Write to Primary OSS ES cluster
    es = Elasticsearch(
    hosts=[{"host": "ip-80-0-18-136.ec2.internal", "port": 9200},
           {"host": "ip-80-0-29-251.ec2.internal", "port": 9200},
           {"host": "ip-80-0-30-161.ec2.internal", "port": 9200},
           {"host": "ip-80-0-28-34.ec2.internal", "port": 9200},
          ],
    http_auth=["elastic", "changeme"],
    )

    # Create client for Kinesis Firehose with delivery stream set to Amazon OpenSearch
    print("create client instance for firehose")
    fh = boto3.client('firehose', region_name='us-east-1',aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"))

    print("opensearch instance created")
    est = pytz.timezone('US/Eastern')

    bt=os.environ.get("TWITTER_API_TOKEN")
    printer = process_tweet(bt)
    printer.sample()

```

Writer -> Opensearch

```
import os
import json
import tweepy
import pytz
from tweepy import OAuthHandler
from tweepy import StreamingClient
from textblob import TextBlob
from elasticsearch import Elasticsearch, RequestsHttpConnection
from datetime import datetime
import requests
from requests_aws4auth import AWS4Auth

# create instance of elasticsearch
region = 'us-east-1'
service = 'es'
awsauth = AWS4Auth(os.environ.get("AWS_ACCESS_KEY_ID"), os.environ.get("AWS_SECRET_ACCESS_KEY"), region, service)

host = 'vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com'

es = Elasticsearch(
    hosts = [{'host': host, 'port': 443}],
    http_auth = awsauth,
    use_ssl = True,
    verify_certs = True,
    connection_class = RequestsHttpConnection
)

est = pytz.timezone('US/Eastern')

class IDPrinter(tweepy.StreamingClient):
  def on_data(self, data):
    # decode json
    dict_data = json.loads(data)

    # pass tweet into TextBlob
    tweet_id = TextBlob(dict_data['data']['id'])
    timestamp = datetime.now().astimezone(est).strftime("%Y-%m-%d %H:%M:%S")
    tweet = TextBlob(dict_data['data']['text'])
    tweetstr = str(tweet)
    user_name = tweetstr[tweetstr.find('@')+1 : tweetstr.find(':')]

    # determine if sentiment is positive, negative, or neutral
    if tweet.sentiment.polarity < 0:
        sentiment = "negative"
    elif tweet.sentiment.polarity == 0:
        sentiment = "neutral"
    else:
        sentiment = "positive"

    # output values
    print("tweet_id: "+ str(tweet_id))
    print("timestamp: " +timestamp)
    print("user_name: " + user_name)
    print("tweet_polarity: " + str(tweet.sentiment.polarity))
    print("tweet_subjectivity: " + str(tweet.sentiment.subjectivity))
    print("sentiment: " + sentiment)

    # index values into OSS Elasticsearch
    es.index(index="data_sentiment",
                 doc_type="test-type",
                 body={"user": user_name,
                       "timestamp": timestamp,
                       "message": dict_data["data"]["text"],
                       "polarity": tweet.sentiment.polarity,
                       "subjectivity": tweet.sentiment.subjectivity,
                       "sentiment": sentiment})

if __name__ == '__main__':

    bt=os.environ.get("TWITTER_API_TOKEN")
    printer = IDPrinter(bt)
    printer = IDPrinter(bt)
    printer.sample()

```

**Amazon Elasticsearch <= 7.1 to Amazon Opensearch**
**/////////////////////////////////////////////////**

Create an index in Open-distro Elasticsearch 5.6

```
curl -XDELETE 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/data_sentiment'

curl -XPUT 'https://vpc-open-distro-es-5-6-lgpve2ddaggepo5jk4ozxszlja.us-east-1.es.amazonaws.com/data_sentiment' --user $AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY --aws-sigv4 "aws:amz:us-east-1:es" -k -H 'Content-Type: application/json' -d '
        {
          "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 2
          },
          "mappings" : {
          "_default_" : {
           "properties" : {
             "user" : {"type": "string"},
             "timestamp" : { "type" : "date", "format" :  "yyyy-MM-dd HH:mm:ss"},
             "tweet" : {"type": "string"},
             "polarity" : {"type" : "double"},
             "subjectivity" : {"type" : "double"},
             "sentiment" : {"type": "string"}
            }
           }
          }
         }
       ';

```

```
python3 es-5.6.py
```

```

curl -X GET 'https://vpc-open-distro-es-5-6-lgpve2ddaggepo5jk4ozxszlja.us-east-1.es.amazonaws.com/data_sentiment/_count' --user $AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY --aws-sigv4 "aws:amz:us-east-1:es" -k
```

2. Upgrade in UI and write during upgrade

```
python3 es-5.6.py

curl -X GET 'https://vpc-open-distro-es-5-6-lgpve2ddaggepo5jk4ozxszlja.us-east-1.es.amazonaws.com/data_sentiment/_count' --user $AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY --aws-sigv4 "aws:amz:us-east-1:es" -k
```

**Apache Solr to Amazon Opensearch**
**/////////////////////////////////**

*Setup Solr Server and Client*
*-----------------------------*

1. Login to EC2 instance “oss-elasticsearch-client-host“
2. Install required dependencies

```
pip3 install pysolr
```

3. Create a Solr core

```
bin/solr create -c data_sentiment -force
bin/solr stop -all
service solr start
```

4. Go to Solr UI and select the core that was created. Select schema. We are going to modify the managed schema and add twitter columns using “Add Field”. Add 5 following fields with field type. Leave other stuff defaulted.

```
    timestamp: pdate
    user_name: string
    polarity: pdouble
    subjectivity: pdouble
    sentiment: string

```

5. Execute Solr client
```
python3 solr.py

```

6. Query from the UI to verify that the records are getting added.

7. Get count of records in the core we are writing to using below command. We will use this count to verify that our migration was successful.

```
sudo yum install -y jq
curl -s --negotiate -u: 'ec2-18-212-174-25.compute-1.amazonaws.com:8983/solr/data_sentiment/query?q=*:*&rows=0' | jq '.response | .numFound'
```

8. To delete all records in a cores

```
{'delete': {'query': '*:*'}}
```

*Start migration process to Amazon Opensearch using Apache Hive (distributed)*
*----------------------------------------------------------------------------*

1. Launch an EMR 6.6 cluster with 3 x r4.2xlarge nodes and Hive installed

2. Copy required JARs in Hive auxlib path

```
aws s3 cp s3://vasveena-scrape/jars/solr-hive-serde-4.0.0.7.2.15.0-147.jar .
aws s3 cp s3://vasveena-scrape/jars/elasticsearch-hadoop-7.10.3-SNAPSHOT.jar .

sudo cp solr-hive-serde-4.0.0.7.2.15.0-147.jar /usr/lib/hive/auxlib
sudo cp elasticsearch-hadoop-7.10.3-SNAPSHOT.jar /usr/lib/hive/auxlib
sudo cp /usr/share/aws/emr/instance-controller/lib/commons-httpclient-3.0.jar /usr/lib/hive/auxlib

sudo chmod 777 /usr/lib/hive/auxlib/solr-hive-serde-4.0.0.7.2.15.0-147.jar
sudo chmod 777 /usr/lib/hive/auxlib/elasticsearch-hadoop-7.10.3-SNAPSHOT.jar
sudo chmod 777 /usr/lib/hive/auxlib/commons-httpclient-3.0.jar
```

3. Login to Hive CLI and create a Hive table for Solr core data_sentiment

```
CREATE EXTERNAL TABLE data_sentiment_solr (`id` string,
`user_name` string,
`tweet_tstamp` string,
`message` string,
`polarity` double,
`subjectivity` double,
`sentiment` string
 )
ROW FORMAT DELIMITED lines terminated by '\n'
STORED BY 'com.lucidworks.hadoop.hive.LWStorageHandler'
TBLPROPERTIES('solr.server.url' = 'http://ec2-54-91-128-241.compute-1.amazonaws.com:8983/solr',
              'solr.collection' = 'data_sentiment',
              'solr.query' = '*:*');
```

4. Make sure you are able to query the table

```
select * from data_sentiment_solr limit 5;
```

5. Create an index in Amazon Opensearch called “data_sentiment_solr” with below schema. You can add extra fields or remove any fields you want.

```
curl -XDELETE -u 'admin:Test123$' 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/data_sentiment_solr'

curl -XPUT -u 'admin:Test123$' 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/data_sentiment_solr' -k -H 'Content-Type: application/json' -d '
        {
          "settings": {
            "number_of_shards": 2,
            "number_of_replicas": 2
          },
          "mappings" : {
           "properties" : {
             "tweet_id": {"type": "text"},
             "user" : {"type": "text"},
             "tweet_tstamp" : { "type" : "date", "format" :  "yyyy-MM-dd HH:mm:ss"},
             "tweet" : {"type": "text"},
             "polarity" : {"type" : "double"},
             "subjectivity" : {"type" : "double"},
             "sentiment" : {"type": "text"},
             "modified_tstamp" : { "type" : "date", "format" :  "yyyy-MM-dd HH:mm:ss"}
            }
           }
         }
       '
```

6. Create a Hive table for Amazon Opensearch index we just created

```
CREATE EXTERNAL TABLE data_sentiment_os (`tweet_id` string,
`user_name` string,
`tweet_tstamp` string,
`message` string,
`polarity` double,
`subjectivity` double,
`sentiment` string,
`modified_tstamp` string
 )
STORED BY 'org.elasticsearch.hadoop.hive.EsStorageHandler'
TBLPROPERTIES(
    'es.nodes' = 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com',
    'es.port' = '443',
    'es.net.http.auth.user' = 'admin',
    'es.net.http.auth.pass' = 'Test123$',
    'es.net.ssl' = 'true',
    'es.nodes.wan.only' = 'true',
    'es.nodes.discovery' = 'false',
    'es.resource' = 'data_sentiment_solr/_doc'
);
```

7. Make sure you are able to query the table without any errors. Table is empty at this point but if you get any errors when you do a select *, check /var/log/hive/user/hadoop/hive.log

8. Try to insert test data  (optional)

insert into table data_sentiment_os values ('0','test','2022-06-28 01:04:55','test from hive','0.0','0.0','neutral','2022-06-28 01:04:55')

9. Now perform insert from Solr Hive table into Amazon Opensearch Hive table

insert into table data_sentiment_os (tweet_id, tweet_tstamp, user_name, message, polarity, subjectivity, sentiment, modified_tstamp) select id, tweet_tstamp, user_name, message, polarity, subjectivity, sentiment, from_unixtime(unix_timestamp()) from data_sentiment_solr;

10. Once job finishes, verify the count between Solr source and Amazon Opensearch destination

```
sar -n DEV 1 3

curl -s --negotiate -u: 'ec2-18-212-174-25.compute-1.amazonaws.com:8983/solr/data_sentiment/query?q=*:*&rows=0' | jq '.response | .numFound'
390

curl -X GET -u 'admin:Test123$' 'https://vpc-opensearch-domain-2-owetvxqg2fuyybzuwlnpuk6pcq.us-east-1.es.amazonaws.com:443/data_sentiment_solr/_count' -k
{"count":390,"_shards":{"total":2,"successful":2,"skipped":0,"failed":0}}
```

*Final Step - Upgrade Clients*
*------------------------------*

Write client -> Apache Solr (sync) -> Amazon Kinesis Firehose (async) -> Amazon OpenSearch

```
import os
import json
import boto3
import tweepy
import pytz
from tweepy import OAuthHandler
from tweepy import StreamingClient
from textblob import TextBlob
from datetime import datetime
import requests
from requests_aws4auth import AWS4Auth
import pysolr

class process_tweet(tweepy.StreamingClient):
  print("in process_tweet")
  def on_data(self, data):
    print("on_data")
    # print(data)
    # decode json
    dict_data = json.loads(data)

    # pass tweet into TextBlob
    tweet_id = TextBlob(dict_data['data']['id'])
    timestamp = datetime.now().astimezone(est).strftime("%Y-%m-%d %H:%M:%S")
    tweet = TextBlob(dict_data['data']['text'])
    tweetstr = str(tweet)
    s = tweetstr.split(':')[0].strip()
    p = s.partition("RT @")
    message = dict_data["data"]["text"].strip('\n').strip()
    #stripped = ''.join(e for e in message if e.isalnum())
    if len(p) >= 2:
        if p[1] == "RT @":
            user_name = p[2]
        else:
            user_name = "none"
    else:
        user_name = "none"

    # determine if sentiment is positive, negative, or neutral
    if tweet.sentiment.polarity < 0:
        sentiment = "negative"
    elif tweet.sentiment.polarity == 0:
        sentiment = "neutral"
    else:
        sentiment = "positive"

    # output values
    print("tweet_id: "+ str(tweet_id))
    print("timestamp: " +timestamp)
    print("user_name: " + user_name)
    print("tweet_polarity: " + str(tweet.sentiment.polarity))
    print("tweet_subjectivity: " + str(tweet.sentiment.subjectivity))
    print("sentiment: " + sentiment)

    final_solr_data = {}
    final_solr_data['id'] = dict_data['data']['id']
    final_solr_data['user_name'] = user_name
    final_solr_data['tweet_tstamp'] = timestamp
    final_solr_data['message'] = message
    final_solr_data['polarity'] = str(tweet.sentiment.polarity)
    final_solr_data['subjectivity'] = str(tweet.sentiment.subjectivity)
    final_solr_data['sentiment'] = sentiment

    final_fh_data = {}
    final_fh_data['tweet_id'] = str(tweet_id)
    final_fh_data['timestamp'] = timestamp
    final_fh_data['user_name'] = user_name
    final_fh_data['tweet_polarity'] = str(tweet.sentiment.polarity)
    final_fh_data['tweet_subjectivity'] = str(tweet.sentiment.subjectivity)
    final_fh_data['sentiment'] = sentiment

    json_solr_data = json.dumps(final_solr_data)
    json_fh_data = json.dumps(final_fh_data)

    # index values into Solr
    solr.add(final_solr_data)

    # Write to Kinesis Firehose with delivery stream set to Amazon OpenSearch
    fh.put_record(
            DeliveryStreamName='PUT-OPS-lVe9k',
            Record={'Data': json_fh_data},
        )

  def on_error(self, status):
    print(status)

if __name__ == '__main__':
#def handler(event, context):
    print("in handler")

    # Create Solr client
    print("create Solr client")
    solr = pysolr.Solr('http://ec2-18-212-174-25.compute-1.amazonaws.com:8983/solr/data_sentiment', always_commit=True)

    # Create client for Kinesis Firehose with delivery stream set to Amazon OpenSearch
    print("create client instance for firehose")
    fh = boto3.client('firehose', region_name='us-east-1',aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"))

    print("opensearch instance created")
    est = pytz.timezone('US/Eastern')

    bt=os.environ.get("TWITTER_API_TOKEN")
    printer = process_tweet(bt)
    printer.sample()

```

Repeat for all Solr cores you want to migrate.
