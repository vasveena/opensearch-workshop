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
