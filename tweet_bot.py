import os
import time
import tweepy
import logging
import openai
import requests
import json
import feedparser
import random
import hashlib
from datetime import datetime, timedelta
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

POSTED_ARTICLES_FILE = 'posted_articles.json'

def get_twitter_client():
    """Initialize Twitter client with API credentials."""
    try:
        # Verify all required environment variables are present
        required_env_vars = [
            'TWITTER_API_KEY',
            'TWITTER_API_SECRET',
            'TWITTER_ACCESS_TOKEN',
            'TWITTER_ACCESS_TOKEN_SECRET'
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        client = tweepy.Client(
            consumer_key=os.getenv('TWITTER_API_KEY'),
            consumer_secret=os.getenv('TWITTER_API_SECRET'),
            access_token=os.getenv('TWITTER_ACCESS_TOKEN'),
            access_token_secret=os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
        )
        return client
    except Exception as e:
        logger.error(f"Error initializing Twitter client: {e}")
        raise

def fetch_cybersecurity_news():
    """Fetch recent cybersecurity news from multiple RSS feeds."""
    try:
        # List of RSS feeds to check
        feeds = [
            {
                'url': 'https://www.bleepingcomputer.com/feed/',
                'name': 'BleepingComputer'
            },
            {
                'url': 'https://www.darkreading.com/rss_simple.asp',
                'name': 'Dark Reading'
            },
            {
                'url': 'https://www.cyberscoop.com/feed/',
                'name': 'CyberScoop'
            },
            {
                'url': 'https://feeds.feedburner.com/TheHackersNews',
                'name': 'The Hacker News'
            },
            {
                'url': 'https://blog.rapid7.com/rss/',
                'name': 'Rapid7 Blog'
            },
            {
                'url': 'https://techcrunch.com/tag/security/feed/',
                'name': 'TechCrunch'
            },
            {
                'url': 'https://www.hackread.com/feed/',
                'name': 'HackRead'
            },
            {
                'url': 'https://krebsonsecurity.com/feed/',
                'name': 'Krebs on Security'
            },
            {
                'url': 'https://threatpost.com/feed/',
                'name': 'Threatpost'
            }
        ]

        # Get current time for age comparison
        current_time = datetime.utcnow()
        all_entries = []

        for feed_info in feeds:
            try:
                logger.info(f"Fetching feed from {feed_info['name']}...")
                
                # Add headers to avoid 403 errors
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                # First try with requests to handle redirects
                response = requests.get(feed_info['url'], headers=headers, timeout=10, allow_redirects=True)
                if response.status_code != 200:
                    logger.warning(f"Failed to fetch {feed_info['name']}: Status {response.status_code}")
                    continue
                
                # Parse the feed content
                feed = feedparser.parse(response.content)
                
                if not feed.entries:
                    logger.warning(f"No entries found in {feed_info['name']}")
                    continue
                
                logger.info(f"Found {len(feed.entries)} entries in {feed_info['name']}")
                
                # Process each entry in the feed
                for entry in feed.entries[:5]:  # Look at top 5 entries from each feed
                    try:
                        # Get publication date
                        if hasattr(entry, 'published_parsed'):
                            pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        elif hasattr(entry, 'updated_parsed'):
                            pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                        else:
                            logger.warning(f"No date found for entry in {feed_info['name']}")
                            continue

                        # Only include entries from the last 24 hours
                        age = current_time - pub_date
                        if age <= timedelta(days=1):
                            # Clean and format the entry
                            title = entry.title.strip()
                            
                            # Try different fields for content
                            description = None
                            for field in ['description', 'summary', 'content']:
                                if hasattr(entry, field):
                                    content = getattr(entry, field)
                                    if isinstance(content, list):  # Handle content list
                                        content = content[0].value
                                    description = content
                                    break
                            
                            if not description:
                                description = title
                            
                            # Clean up description
                            description = ' '.join(description.split())  # Clean up whitespace
                            
                            all_entries.append({
                                'title': title,
                                'description': description[:250],  # Limit description length
                                'link': entry.link,
                                'source': feed_info['name'],
                                'published': pub_date,
                                'age_minutes': age.total_seconds() / 60
                            })
                            logger.info(f"Found article: {title}")
                    except Exception as e:
                        logger.warning(f"Error processing entry from {feed_info['name']}: {str(e)}")
                        continue
            
            except Exception as e:
                logger.warning(f"Error fetching feed {feed_info['name']}: {str(e)}")
                continue

        if all_entries:
            # Sort by publication date (newest first)
            all_entries.sort(key=lambda x: x['published'], reverse=True)
            
            # Get articles from the last 12 hours for more variety
            recent_entries = [
                entry for entry in all_entries 
                if (datetime.utcnow() - entry['published']).total_seconds() / 3600 <= 12
            ]
            
            if recent_entries:
                # Randomly select from recent articles
                selected_entry = random.choice(recent_entries)
                logger.info(f"Randomly selected news from {selected_entry['source']}: {selected_entry['title']}")
                logger.info(f"Published: {selected_entry['published']}")
                logger.info(f"Available articles in last 12 hours: {len(recent_entries)}")
                return selected_entry
            else:
                # Fallback to most recent if no articles in last 12 hours
                selected_entry = all_entries[0]
                logger.info(f"No articles in last 12 hours, using most recent from {selected_entry['source']}: {selected_entry['title']}")
                logger.info(f"Published: {selected_entry['published']}")
                return selected_entry
        
        logger.warning("No recent news found from any feed")
        return None

    except Exception as e:
        logger.error(f"Error in feed fetching: {str(e)}")
        return None

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def generate_tweet_content():
    """Generate a tweet by summarizing cybersecurity news article."""
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY environment variable")
            
        # Ensure API key is a clean string without any encoding issues
        api_key = api_key.strip()
        if not api_key.startswith('sk-'):
            raise ValueError("Invalid OpenAI API key format. Key should start with 'sk-'")

        openai.api_key = api_key
        
        # Fetch latest news
        news = fetch_cybersecurity_news()
        
        if not news:
            logger.warning("No recent news found")
            return None

        # Check for duplicate article in local history
        article_hash = get_article_hash(news)
        posted_articles = load_posted_articles()
        if article_hash in posted_articles:
            logger.info(f"Article already posted (local history): {news['title']} ({news['link']})")
            return None

        logger.info(f"Summarizing article from {news['source']}")
        
        prompt = f"""Summarize this cybersecurity article into a concise tweet:

Title: {news['title']}
Source: {news['source']}
Content: {news['description']}

Guidelines:
1. Extract the most important security finding/alert/update
2. Focus on impact or actionable insight
3. Keep it factual and specific to the article
4. Do not add generic advice
5. Do not use hashtags - they will be added later
6. Keep it under 200 characters to leave room for the URL

Format:
🚨 [Key finding/alert]
[Brief impact or importance]"""

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a cybersecurity news editor who creates clear, factual summaries. Focus only on the specific news provided."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.5,  # Lower temperature for more focused summaries
            request_timeout=30
        )
        
        tweet_content = response.choices[0].message['content'].strip()
        
        # Combine content with URL
        max_length = 280 - len(news['link']) - 1  # 1 char for newline
        if len(tweet_content) > max_length:
            tweet_content = tweet_content[:max_length-3] + "..."
        
        final_tweet = f"{tweet_content}\n{news['link']}"
        
        logger.info(f"Generated tweet content: {final_tweet}")
        return final_tweet, article_hash

    except Exception as e:
        logger.error(f"Error generating tweet content: {str(e)}")
        raise

def check_rate_limits(client):
    """Check Twitter rate limits before posting."""
    try:
        # Get rate limit status
        response = client.get_users_tweets(id=client.get_me().data.id)
        remaining = int(response.rate_limit_remaining)
        logger.info(f"Rate limit remaining: {remaining}")
        
        if remaining < 2:  # Keep a buffer
            reset_time = int(response.rate_limit_reset)
            wait_time = reset_time - time.time()
            if wait_time > 0:
                logger.warning(f"Rate limit nearly exhausted. Waiting {wait_time:.0f} seconds...")
                time.sleep(wait_time + 1)  # Add 1 second buffer
        return True
    except Exception as e:
        logger.warning(f"Error checking rate limits: {e}")
        return False

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=10),
    retry=retry_if_exception_type((tweepy.errors.TooManyRequests, tweepy.errors.TwitterServerError))
)
def get_recent_tweets(client, max_results=20):
    """Get recent tweets from the user's timeline with retry logic."""
    try:
        user_id = client.get_me().data.id
        tweets = client.get_users_tweets(
            id=user_id,
            max_results=max_results,
            tweet_fields=['created_at', 'text']
        )
        return tweets.data if tweets.data else []
    except tweepy.errors.TooManyRequests as e:
        logger.warning(f"Rate limit exceeded while fetching tweets: {e}")
        raise
    except tweepy.errors.TwitterServerError as e:
        logger.warning(f"Twitter server error while fetching tweets: {e}")
        raise
    except Exception as e:
        logger.warning(f"Error fetching recent tweets: {e}")
        return []

def is_article_already_posted(client, news):
    """Check if an article has already been posted by checking recent tweets."""
    try:
        recent_tweets = get_recent_tweets(client)
        
        if not recent_tweets:
            logger.warning("Could not fetch recent tweets, proceeding with local history check only")
            return False
        
        # Create a simple identifier for the article
        article_title = news.get('title', '').lower()
        article_link = news.get('link', '')
        
        for tweet in recent_tweets:
            tweet_text = tweet.text.lower()
            # Check if the tweet contains the article link
            if article_link in tweet_text:
                logger.info(f"Article already posted on Twitter: {news.get('title', '')}")
                return True
            # Check if the tweet contains the article title (partial match)
            if article_title and len(article_title) > 10:
                # Use a substring of the title for matching
                title_substring = article_title[:30]  # First 30 chars
                if title_substring in tweet_text:
                    logger.info(f"Article title already posted on Twitter: {news.get('title', '')}")
                    return True
        
        return False
    except tweepy.errors.TooManyRequests as e:
        logger.warning(f"Rate limit exceeded while checking for duplicates: {e}")
        # Fall back to local history only
        return False
    except tweepy.errors.TwitterServerError as e:
        logger.warning(f"Twitter server error while checking for duplicates: {e}")
        # Fall back to local history only
        return False
    except Exception as e:
        logger.warning(f"Error checking if article already posted: {e}")
        return False

@retry(
    stop=stop_after_attempt(5),  # Increase max attempts
    wait=wait_exponential(multiplier=60, min=60, max=3600),  # Wait between 1-60 minutes
    retry=retry_if_exception_type(tweepy.errors.TooManyRequests)
)
def post_tweet():
    """Generate and post a tweet with retry logic."""
    try:
        # Get Twitter client
        twitter = get_twitter_client()
        
        # Check rate limits before proceeding
        check_rate_limits(twitter)
        
        # Fetch news for Twitter feed checking
        news = fetch_cybersecurity_news()
        if not news:
            logger.warning("No recent news found")
            return None
            
        # Check if article already posted on Twitter (with fallback to local history)
        if is_article_already_posted(twitter, news):
            logger.info(f"Article already posted on Twitter, skipping: {news['title']}")
            return None
        
        # Generate tweet content
        result = generate_tweet_content()
        if not result:
            logger.warning("No tweet content generated, skipping post")
            return None
        if isinstance(result, tuple):
            tweet_content, article_hash = result
        else:
            tweet_content = result
            article_hash = None
            
        logger.info(f"Generated tweet: {tweet_content}")
        
        try:
            # Post tweet with error handling
            response = twitter.create_tweet(text=tweet_content)
            tweet_id = response.data['id']
            logger.info(f"Successfully posted tweet with ID: {tweet_id}")
            # Save posted article hash
            if article_hash:
                save_posted_article(article_hash)
            # Add delay after successful post to help with rate limiting
            time.sleep(5)
            
            return tweet_id
            
        except tweepy.errors.TooManyRequests as e:
            logger.warning(f"Rate limit exceeded. Waiting before retry. Error: {str(e)}")
            raise  # Let tenacity handle the retry
        except tweepy.errors.TwitterServerError as e:
            logger.error(f"Twitter server error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error posting tweet: {str(e)}")
            raise
        
    except Exception as e:
        logger.error(f"Error in post_tweet: {str(e)}")
        raise

def load_posted_articles():
    """Load the set of posted article hashes from the local file."""
    if not os.path.exists(POSTED_ARTICLES_FILE):
        return set()
    try:
        with open(POSTED_ARTICLES_FILE, 'r') as f:
            data = json.load(f)
            return set(data)
    except Exception as e:
        logger.warning(f"Could not load posted articles file: {e}")
        return set()

def save_posted_article(article_hash):
    """Save a new article hash to the local file."""
    posted = load_posted_articles()
    posted.add(article_hash)
    try:
        with open(POSTED_ARTICLES_FILE, 'w') as f:
            json.dump(list(posted), f)
    except Exception as e:
        logger.warning(f"Could not save posted article: {e}")

def get_article_hash(news):
    """Generate a unique hash for an article based on its title and link."""
    unique_str = f"{news.get('title','')}|{news.get('link','')}"
    return hashlib.sha256(unique_str.encode('utf-8')).hexdigest()

if __name__ == "__main__":
    try:
        logger.info("Starting tweet bot...")
        
        # Add random initial delay between 1-5 minutes to help prevent concurrent runs
        initial_delay = random.randint(60, 300)
        logger.info(f"Adding initial delay of {initial_delay} seconds...")
        time.sleep(initial_delay)
        
        # Verify all environment variables are set
        required_vars = [
            'TWITTER_API_KEY',
            'TWITTER_API_SECRET',
            'TWITTER_ACCESS_TOKEN',
            'TWITTER_ACCESS_TOKEN_SECRET',
            'OPENAI_API_KEY'
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        tweet_id = post_tweet()
        logger.info("Tweet bot completed successfully")
    except tweepy.errors.TooManyRequests as e:
        logger.error(f"Rate limit exceeded: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Tweet bot failed: {str(e)}")
        raise 