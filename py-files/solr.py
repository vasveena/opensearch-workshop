import re
import json
import tweepy
import pytz
from tweepy import OAuthHandler
from tweepy import StreamingClient
from textblob import TextBlob
from datetime import datetime
import pysolr

# create instance of solr

solr = pysolr.Solr('http://ec2-18-212-174-25.compute-1.amazonaws.com:8983/solr/data_sentiment', always_commit=True)

# Do a health check.
solr.ping()

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
    print("message: " + message)
    print("tweet_polarity: " + str(tweet.sentiment.polarity))
    print("tweet_subjectivity: " + str(tweet.sentiment.subjectivity))
    print("sentiment: " + sentiment)

    # create a JSON to write to Solr 
    kv_data = {}
    kv_data['id'] = dict_data['data']['id']
    kv_data['user_name'] = user_name
    kv_data['tweet_tstamp'] = timestamp
    kv_data['message'] = message
    kv_data['polarity'] = str(tweet.sentiment.polarity)
    kv_data['subjectivity'] = str(tweet.sentiment.subjectivity)
    kv_data['sentiment'] = sentiment
    json_data = json.dumps(kv_data)

    # index values into Solr
    solr.add(kv_data)
    
if __name__ == '__main__':

    bt=os.environ.get("TWITTER_API_TOKEN")
    printer = IDPrinter(bt)
    printer.sample()
