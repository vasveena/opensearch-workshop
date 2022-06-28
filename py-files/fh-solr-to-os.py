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
