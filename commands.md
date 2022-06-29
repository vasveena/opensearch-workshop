**OSS Elasticsearch 5.6 to Amazon Opensearch 1.2** <br>
**//////////////////////////////////////////////////////** <br>

**Upgrade from OSS ES 5.6 to OSS ES 6.8 (min version required to migrate to Amazon OS)** <br>

*Step 0 - Building OSS Elasticsearch cluster* <br>
*------------------------------------------------------------* <br>

Create 3 x Amazon Linux 2 EC2 instances and run the following commands on all of them.

```
sudo yum install java-1.8.0 -y

sudo setfacl -R -m u:ec2-user:rwx /mnt
mkdir -p /mnt/elasticsearch/data
mkdir -p /mnt/elasticsearch/logs

sudo sysctl -w vm.max_map_count=262144
sudo sysctl -w fs.file-max=65536

sudo su
echo "ec2-user   soft    nofile          65536" >> /etc/security/limits.conf
echo "ec2-user   hard    nofile          65536" >> /etc/security/limits.conf
echo "ec2-user   memlock unlimited" >> /etc/security/limits.conf

exit # as sudo
exit # as ec2-user
<re-login / SSH again>

wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-5.6.16.tar.gz
wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-5.6.16.tar.gz.sha512

sudo yum install perl-Digest-SHA -y
shasum -a 512 -c elasticsearch-5.6.16.tar.gz.sha512

tar -xzf elasticsearch-5.6.16.tar.gz
cd elasticsearch-5.6.16

echo 'export ES_HOME=/home/ec2-user/elasticsearch-5.6.16/' >> ~/.bashrc
source ~/.bashrc

# Change node.name for each EC2 instance
echo "cluster.name: oss-es-cluster-2" >> $ES_HOME/config/elasticsearch.yml
echo "node.name: node-1" >> $ES_HOME/config/elasticsearch.yml
echo "node.master: true" >> $ES_HOME/config/elasticsearch.yml
echo "node.data: true" >> $ES_HOME/config/elasticsearch.yml
echo "path.data: /mnt/elasticsearch/data/" >> $ES_HOME/config/elasticsearch.yml
echo "path.logs: /mnt/elasticsearch/logs/" >> $ES_HOME/config/elasticsearch.yml
echo "discovery.zen.minimum_master_nodes: 3" >> $ES_HOME/config/elasticsearch.yml
echo "discovery.zen.ping.unicast.hosts: [\"80.0.24.8:9300\", \"80.0.25.179:9300\",\"80.0.24.226:9300\"]" >> $ES_HOME/config/elasticsearch.yml
echo "network.bind_host: 0.0.0.0" >> $ES_HOME/config/elasticsearch.yml
echo "network.publish_host: $(hostname -f)" >> $ES_HOME/config/elasticsearch.yml
echo "transport.tcp.port: 9300" >> $ES_HOME/config/elasticsearch.yml
echo "transport.host: $(hostname -I | awk '{print $1}')" >> /$ES_HOME/config/elasticsearch.yml

/home/ec2-user/elasticsearch-5.6.16/bin/elasticsearch > ~/elastic.out 2>&1 &

```

Once all above commands are executed in all the instances, run the below command on any one of the nodes and make sure OSS ES cluster is installed properly.

```
curl -u elastic:changeme 127.0.0.1:9200

Output:
{
  "name" : "node-1",
  "cluster_name" : "oss-es-cluster-2",
  "cluster_uuid" : "QKbdSxaBSZmPsuyZrIO84A",
  "version" : {
    "number" : "5.6.16",
    "build_hash" : "3a740d1",
    "build_date" : "2019-03-13T15:33:36.565Z",
    "build_snapshot" : false,
    "lucene_version" : "6.6.1"
  },
  "tagline" : "You Know, for Search"
}

curl -u elastic:changeme -XGET -H "Content: application/json" "127.0.0.1:9200/_cluster/health?pretty"

```

Create an index in the OSS ES cluster. Run these commands on any one of the OSS ES EC2 nodes.

```
# Deleting index. Command for my use. No need to run it.
curl -XDELETE http://127.0.0.1:9200/data_sentiment

# Creating a new index with schema
curl -XPUT http://127.0.0.1:9200/data_sentiment -d '
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

# Get index
curl -XGET "http://127.0.0.1:9200/data_sentiment"

```

Install Kibana on any one of the 3 EC2 instances - Optional

```

cd ~
wget https://artifacts.elastic.co/downloads/kibana/kibana-5.6.16-linux-x86_64.tar.gz
wget https://artifacts.elastic.co/downloads/kibana/kibana-5.6.16-linux-x86_64.tar.gz.sha512
shasum -a 512 -c kibana-5.6.16-linux-x86_64.tar.gz.sha512
tar -xzf kibana-5.6.16-linux-x86_64.tar.gz
cd kibana-5.6.16-linux-x86_64/
echo "server_host: 0.0.0.0" >> /home/ec2-user/kibana-5.6.16-linux-x86_64/config/kibana.yml
/home/ec2-user/kibana-5.6.16-linux-x86_64/bin/kibana > ~/kibana.log 2>&1 &

```

Create a client that ingests Twitter API data into OSS ES cluster. For this, create another EC2 instance (client host) and install required packages.

```
pip3 install tweepy==4.10.0
pip3 install elasticsearch==5.5.3
pip3 install textblob
pip3 install pytz

```

Run the following Python (v3.7) program for indexing sentiment analysis data from Twitter APIs into the OSS ES cluster.

```
import os
import json
import tweepy
import pytz
from tweepy import OAuthHandler
from tweepy import StreamingClient
from textblob import TextBlob
from elasticsearch import Elasticsearch
from datetime import datetime

# create instance of elasticsearch
# replace with your hosts
es = Elasticsearch(
    hosts=[{"host": "ip-80-0-24-8.ec2.internal", "port": 9200},
           {"host": "ip-80-0-25-179.ec2.internal", "port": 9200},
           {"host": "ip-80-0-24-226.ec2.internal", "port": 9200},
          ],
    http_auth=["elastic", "changeme"],
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
    printer.sample()

```

Make sure that data is getting written using count API on one of the OSS ES EC2 nodes. You can also use Kibana to search the documents.

```
curl -X GET "127.0.0.1:9200/data_sentiment/_count"

```

*Step 1 - Take a snapshot of your OSS Elasticsearch cluster (Optional)* <br>
*------------------------------------------------------------* <br>

Run the below commands on all nodes. To take snapshot of OSS ES 5.6 cluster for disaster recovery during rolling upgrade.

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

```
Now run the below commands on any one of the OSS ES nodes.

```
# Following command returns empty
curl -XGET http://`hostname -f`:9200/_snapshot/_all?pretty=true
{}

# Create snapshot in S3

curl -XPUT http://`hostname -f`:9200/_snapshot/s3_backup -d'
{
  "type": "s3",
  "settings": {
    "bucket": "oss-es-snapshots-2"
  }
}'

# Verify that snapshot is created

curl -XGET http://`hostname -f`:9200/_snapshot/_all?pretty=true

# Start your snapshot

curl -X PUT "`hostname -f`:9200/_snapshot/s3_backup/snapshot_1?wait_for_completion=false"

# Check snapshot status
curl -X GET "`hostname -f`:9200/_snapshot/s3_backup/snapshot_1?pretty=true"

```

*Step 2 - Perform Rolling Upgrades from 5.x to 6.x* <br>
*-----------------------------------------------------* <br>

Rolling upgrade involves upgrading ES version one node at a time and re-starting. Please note that if you do not want any downtime, you need to make sure that number of mandated masters is less than total number of masters - 1.

1. Disable shard allocation to avoid high IO cost during shard replication from node currently undergoing rolling upgrade to other nodes in the cluster.

```
curl -X PUT http://`hostname -f`:9200/_cluster/settings -d '
{
  "persistent": {
    "cluster.routing.allocation.enable": "primaries"
  }
}'

```

2. Stop non-essential indexing and perform a synced flush (optional). While you can continue indexing during the upgrade, shard recovery is much faster if you temporarily stop non-essential indexing.

```
curl -X POST http://`hostname -f`:9200/_flush/synced

# Get current version before proceeding with upgrade

curl -X GET "http://`hostname -f`:9200?pretty"
Output:
{
  "name" : "node-1",
  "cluster_name" : "oss-es-cluster-2",
  "cluster_uuid" : "QKbdSxaBSZmPsuyZrIO84A",
  "version" : {
    "number" : "5.6.16",
    "build_hash" : "3a740d1",
    "build_date" : "2019-03-13T15:33:36.565Z",
    "build_snapshot" : false,
    "lucene_version" : "6.6.1"
  },
  "tagline" : "You Know, for Search"
}
```

3. Run the following commands on ALL the OSS Elasticsearch nodes - one by one. DO NOT run these commands on more than one node simultaneously.

```
# Download latest minor version from OSS Elasticsearch 6.8.x and verify checksum

cd ~

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

echo "cluster.name: oss-es-cluster-2" >> $ES_HOME/config/elasticsearch.yml
echo "node.name: node-3" >> $ES_HOME/config/elasticsearch.yml
echo "node.master: true" >> $ES_HOME/config/elasticsearch.yml
echo "node.data: true" >> $ES_HOME/config/elasticsearch.yml
echo "path.data: /mnt/elasticsearch/data/" >> $ES_HOME/config/elasticsearch.yml
echo "path.logs: /mnt/elasticsearch/logs/" >> $ES_HOME/config/elasticsearch.yml
echo "discovery.zen.minimum_master_nodes: 3" >> $ES_HOME/config/elasticsearch.yml
echo "discovery.zen.ping.unicast.hosts: [\"80.0.24.8:9300\", \"80.0.25.179:9300\",\"80.0.24.226:9300\"]" >> $ES_HOME/config/elasticsearch.yml
echo "network.bind_host: 0.0.0.0" >> $ES_HOME/config/elasticsearch.yml
echo "network.publish_host: $(hostname -f)" >> $ES_HOME/config/elasticsearch.yml
echo "transport.tcp.port: 9300" >> $ES_HOME/config/elasticsearch.yml
echo "transport.host: $(hostname -I | awk '{print $1}')" >> $ES_HOME/config/elasticsearch.yml

# Stop current ES process
pkill -f elasticsearch

# Start new ES process
$ES_HOME/bin/elasticsearch > ~/elastic-6.out 2>&1 &

```

4. Once you have done the above steps for ALL the nodes, make sure the cluster version is changed to 6.8.23

```
curl -X GET "http://`hostname -f`:9200?pretty"
Output:
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
curl -X PUT http://127.0.0.1:9200/_cluster/settings -H 'Content-Type: application/json' -d '
{
  "persistent": {
    "cluster.routing.allocation.enable": null
  }
}'

curl -X GET http://`hostname -f`:9200/_cat/recovery?pretty

```

6. Install and upgrade s3 plugin and restart elasticsearch on all nodes. This step needs to be for every plugin. In our case, we only used S3 plugin.

```
# Re-install S3 repo on all ES nodes

$ES_HOME/bin/elasticsearch-plugin install repository-s3

# Create Keystore to save your access/secret key of s3 on ALL ES nodes
# Get STS creds from Isengard or create user and specify credentials

$ES_HOME/bin/elasticsearch-keystore create
$ES_HOME/bin/elasticsearch-keystore add s3.client.default.access_key
$ES_HOME/bin/elasticsearch-keystore add s3.client.default.secret_key

# Stop current ES process
pkill -f elasticsearch

# Start new ES process
$ES_HOME/bin/elasticsearch > ~/elastic-6.out 2>&1 &

```

*Step 3 - Re-index documents* <br>
*----------------------------* <br>

Since we moved from 5.x to 6.x, we need to re-index the documents. The clients will work fine without this step but it may cause some compatibility issues down the line. For instance, datatype “string” has to be changed to “text”. This step will take a while to complete based on the index size.

```
# Create new index using one of the ES nodes
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

curl -XPUT http://`hostname -f`:9200/_snapshot/s3_backup -H 'Content-Type: application/json' -d'
 {
   "type": "s3",
   "settings": {
    "bucket": "oss-es-snapshots-2"
  }
}'

```

*Step 4 - Test Client program (Optional)* <br>
*----------------------------------------* <br>

Run client twitter API program and verify that there are no errors or see if the count is getting increased

```
curl -X GET "localhost:9200/data_sentiment-6/_count"

```

**Migrate from OSS Elasticsearch 6.8 to Opensearch 1.2** <br>
**-----------------------------------------------------** <br>

*Step 5 - Create OpenSearch cluster* <br>
*----------------------------------------* <br>

In Amazon OpenSearch Management Console, create your Amazon OpenSearch 1.2 domain within a VPC. I used master user with password to make it easy. But it is very much recommended to use IAM credentials with SAML or AWS Cognito or FGAC. Please refer to this documentation (https://docs.aws.amazon.com/opensearch-service/latest/developerguide/dashboards.html) for more details.

Using local port forwarding, check if you are able to access your domain. For this, you need to create an EC2 instance in a public subnet with same network settings. Or use the ES client instance created earlier.

```
ssh -i ~/awspsaeast.pem ec2-user@ec2-3-83-111-79.compute-1.amazonaws.com -N -L 9200:vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443
```

Access the cluster and dashboards in browser.

https://localhost:9200
https://localhost:9200/_dashboards

*Step 6 - Take a snapshot of source index* <br>
*----------------------------------------* <br>

First step is to take snapshot of the source OSS cluster. This time, we will change the snapshot name to snapshot_2.

```
# Verify that S3 snapshot exists. If not, create it.

curl -XGET http://`hostname -f`:9200/_snapshot/_all

# Start your snapshot with a different snapshot ID (snapshot_2)

curl -X PUT "http://`hostname -f`:9200/_snapshot/s3_backup/snapshot_2?wait_for_completion=false"

# Check snapshot status
curl -X GET "http://`hostname -f`:9200/_snapshot/s3_backup/snapshot_2"

curl -XPUT http://`hostname -f`:9200/_snapshot/s3_backup_2 -H 'Content-Type: application/json' -d'
 {
   "type": "s3",
   "settings": {
    "bucket": "oss-es-snapshots-2"
  }}'


```

You can restore snapshot directly from S3 using _restore API. But it will be a point-in-time snapshot.

*Step 7 - Configure role mapping for manual snapshot* <br>
*-----------------------------------------------------* <br>

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
                "arn:aws:s3:::oss-es-snapshots",
                "arn:aws:s3:::oss-es-snapshots-2"
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
                "arn:aws:s3:::oss-es-snapshots/*",
                "arn:aws:s3:::oss-es-snapshots-2/*"
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

2. Create a user “opensearch-superuser” and provide following permissions. We will use this user’s credentials to sign requests for using snapshot API.

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
            "Resource": [
                "arn:aws:es:us-east-1:413094830157:domain/opensearch-domain-2/*",
                "arn:aws:us-east-1:region:413094830157:domain/opensearch-domain-66/*"
            ]
        }
    ]
}

```

3. Go to Opensearch dashboards → Security → Roles → search for “manage_snapshots” → select manage_snapshots → Mapped Users. Add the user’s ARN.

Users - arn:aws:iam::413094830157:user/opensearch-superuser
Backend roles - arn:aws:iam::413094830157:role/opensearch-s3-role

Also provide * access to Firehose service role (used for later)
arn:aws:iam::413094830157:role/service-role/KinesisFirehoseServiceRole-PUT-OPS-4WTZi-us-east-1-1656410458234

*Important: For any snapshot operation in Amazon Opensearch we need to sign all our snapshot requests using SDK or Rest API*

We will use boto3 client to create S3 index. You cannot use cURL or even the dashboard here because Amazon OpenSearch requires you to sign your request. You can use any AWS SDK or rest API like Postman that allows AWS signature.

If we do not sign our requests, we will get the below error.

```
curl -XPOST -u 'admin:Test123$' 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/_snapshot/s3-repository/snapshot-2/_restore'
{"error":{"root_cause":[{"type":"security_exception","reason":"no permissions for [] and User [name=admin, backend_roles=[], requestedTenant=null]"}],"type":"security_exception","reason":"no permissions for [] and User [name=admin, backend_roles=[], requestedTenant=null]"},"status":403}

```

*Step 8 - Create an S3 repository in Opensearch cluster* <br>
*-----------------------------------------------------* <br>

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

host = 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/' # include https:// and trailing /
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

curl -XGET -u 'admin:Test123$' 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/_snapshot/s3-repository/snapshot_2/'

*Step 9 - Restore from snapshot* <br>
*--------------------------------* <br>

Now let’s restore the index “data_sentiment”. We cannot restore other indexes because we did not reindex them from OSS Elasticsearch 5.6.16 to 6.8. However, you can restore all indexes at the same time if you re-indexed all of them to 6.8.

```
# Restore from S3 snapshot

import os
import boto3
import requests
from requests_aws4auth import AWS4Auth

host = 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/' # include https:// and trailing /
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

*Step 10 - Validate Restoration* <br>
*--------------------------------* <br>

Verify the count of documents between source and destination

```
curl -X GET 'ip-80-0-24-8.ec2.internal:9200/data_sentiment-6/_count' -k
curl -X GET -u 'admin:Test123$' 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/data_sentiment-6/_count' -k
```

*Final Step - Upgrade Clients* <br>
*--------------------------------* <br>

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
        hosts=[{"host": "ip-80-0-24-8.ec2.internal", "port": 9200},
               {"host": "ip-80-0-25-179.ec2.internal", "port": 9200},
               {"host": "ip-80-0-24-226.ec2.internal", "port": 9200},
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

Verify that the counts are increasing (after buffer timeout)

```
curl -X GET 'ip-80-0-24-8.ec2.internal:9200/data_sentiment-6/_count' -k
curl -X GET -u 'admin:Test123$' 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/data_sentiment-6/_count' -k

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

host = 'vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com'

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

Verify that the counts are increasing

```
curl -X GET -u 'admin:Test123$' 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/data_sentiment-6/_count' -k

```

**Amazon Elasticsearch <= 7.1 to Amazon Opensearch** <br>
**/////////////////////////////////////////////////** <br>

1. Create an index in Open-distro Elasticsearch 5.6

```
curl -XDELETE 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/data_sentiment'

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

Run ingestion client for indexing documents into Amazon Elasticsearch 5.6

```
python3 es-5.6.py

```

Get count during writes

```

curl -X GET 'https://vpc-open-distro-es-5-6-lgpve2ddaggepo5jk4ozxszlja.us-east-1.es.amazonaws.com/data_sentiment/_count' --user $AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY --aws-sigv4 "aws:amz:us-east-1:es" -k
```

2. Upgrade in UI to Amazon Elasticsearch 6.8 and perform write during upgrade

```
python3 es-5.6.py

```

Get count during writes

```
curl -X GET 'https://vpc-open-distro-es-5-6-lgpve2ddaggepo5jk4ozxszlja.us-east-1.es.amazonaws.com/data_sentiment/_count' --user $AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY --aws-sigv4 "aws:amz:us-east-1:es" -k
```

**Apache Solr to Amazon Opensearch** <br>
**/////////////////////////////////** <br>

*Step 0 - Install SolrCloud on EC2*<br>
*-------------------------------------*<br>

Create 3 X EC2 instances and install Apache Solr on them.

```
sudo yum install java-11-amazon-corretto -y
java -version

sudo su
cd ~
wget http://archive.apache.org/dist/lucene/solr/8.6.2/solr-8.6.2.tgz
wget https://archive.apache.org/dist/zookeeper/zookeeper-3.5.7/apache-zookeeper-3.5.7-bin.tar.gz

tar xfvz solr*.tgz
tar xfvz apache-zookeeper-*.tar.gz

cd solr-*/bin
./install_solr_service.sh /root/solr*.tgz -n

sed -i "s|#SOLR_HOST.*|SOLR_HOST=`curl -s http://169.254.169.254/latest/meta-data/public-hostname`|g" /etc/default/solr.in.sh

# Replace with your EC2 instances public DNS
sed -i 's|#ZK_HOST.*|ZK_HOST="ec2-18-212-174-25.compute-1.amazonaws.com:2181,ec2-54-91-128-241.compute-1.amazonaws.com:2181,ec2-54-81-141-240.compute-1.amazonaws.com:2181"|g' /etc/default/solr.in.sh


mv /root/apache-zookeeper-*-bin /opt/zookeeper
cd /opt/zookeeper
mkdir /opt/zookeeper/data

# Change to 2 and 3 for solr-node-2 and solr-node-3 respectively
echo "1" > /opt/zookeeper/data/myid

cp /opt/zookeeper/conf/zoo_sample.cfg /opt/zookeeper/conf/zoo.cfg
sed -i 's|#autopurge|autopurge|g' /opt/zookeeper/conf/zoo.cfg
sed -i 's|dataDir.*|dataDir=/opt/zookeeper/data|g' /opt/zookeeper/conf/zoo.cfg
echo "server.1=ec2-18-212-174-25.compute-1.amazonaws.com:2888:3888" >> /opt/zookeeper/conf/zoo.cfg
echo "server.2=ec2-54-91-128-241.compute-1.amazonaws.com:2888:3888" >> /opt/zookeeper/conf/zoo.cfg
echo "server.3=ec2-54-81-141-240.compute-1.amazonaws.com:2888:3888" >> /opt/zookeeper/conf/zoo.cfg

cd /opt/zookeeper/bin
bash zkServer.sh start

service solr start
```

*Step 1 - Setup Solr Server and Client* <br>
*-----------------------------* <br>

1. Login to EC2 instance “oss-elasticsearch-client-host“
2. Install required dependencies

```
pip3 install pysolr

```

3. Create a Solr core on one of the Solr EC2 instances

```
sudo su
/opt/solr-8.6.2/bin/solr delete -c data_sentiment
/opt/solr-8.6.2/bin/solr create -c data_sentiment -force
/opt/solr-8.6.2/bin/solr stop -all
service solr start

```

4. Go to Solr UI and select the core that was created. Select schema. We are going to modify the managed schema and add twitter columns using “Add Field”. Add 5 following fields with field type. Leave other stuff defaulted.

```
    tweet_tstamp: string
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

8. To delete all records in a core

```
# For reference. Do not run this.
{'delete': {'query': '*:*'}}
```

*Step 2 - Start migration process to Amazon Opensearch using Apache Hive (distributed)*<br>
*----------------------------------------------------------------------------*<br>

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

ls -l /usr/lib/hive/auxlib/

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
TBLPROPERTIES('solr.server.url' = 'http://ec2-18-212-174-25.compute-1.amazonaws.com:8983/solr',
              'solr.collection' = 'data_sentiment',
              'solr.query' = '*:*');
```

4. Make sure you are able to query the table

```
select * from data_sentiment_solr limit 5;
```

5. Create an index in Amazon Opensearch called “data_sentiment_solr” with below schema. You can add extra fields or remove any fields you want.

```
curl -XDELETE -u 'admin:Test123$' 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/data_sentiment_solr'

curl -XPUT -u 'admin:Test123$' 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/data_sentiment_solr' -k -H 'Content-Type: application/json' -d '
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
             "polarity" : {"type" : "float"},
             "subjectivity" : {"type" : "float"},
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
`polarity` float,
`subjectivity` float,
`sentiment` string,
`modified_tstamp` string
 )
STORED BY 'org.elasticsearch.hadoop.hive.EsStorageHandler'
TBLPROPERTIES(
    'es.nodes' = 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com',
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

```
insert into table data_sentiment_os values ('0','test','2022-06-28 01:04:55','test from hive','0.0','0.0','neutral','2022-06-28 01:04:55')
```

9. Now perform insert from Solr Hive table into Amazon Opensearch Hive table

```

insert into table data_sentiment_os (tweet_id, tweet_tstamp, user_name, message, polarity, subjectivity, sentiment, modified_tstamp) select id, tweet_tstamp, user_name, message, polarity, subjectivity, sentiment, from_unixtime(unix_timestamp()) from data_sentiment_solr;

```

10. Once job finishes, verify the count between Solr source and Amazon Opensearch destination

```
sar -n DEV 1 3

curl -s --negotiate -u: 'ec2-18-212-174-25.compute-1.amazonaws.com:8983/solr/data_sentiment/query?q=*:*&rows=0' | jq '.response | .numFound'
390

curl -X GET -u 'admin:Test123$' 'https://vpc-opensearch-domain-66-2cojbcwgonrbsgwadq524hrgoi.us-east-1.es.amazonaws.com:443/data_sentiment_solr/_count?pretty' -k
{"count":390,"_shards":{"total":2,"successful":2,"skipped":0,"failed":0}}
```

*Final Step - Upgrade Clients*<br>
*------------------------------*<br>

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
