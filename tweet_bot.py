import os
import time
import tweepy
import logging
import openai
import requests
import json
import feedparser
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
            
            # Get the most recent relevant entry
            latest_entry = all_entries[0]
            logger.info(f"Selected latest news from {latest_entry['source']}: {latest_entry['title']}")
            return latest_entry
        
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
        
        # Add hashtags based on content
        hashtags = "#CyberSecurity"
        if 'ransomware' in tweet_content.lower() or 'ransom' in tweet_content.lower():
            hashtags += " #Ransomware"
        elif 'breach' in tweet_content.lower() or 'leak' in tweet_content.lower():
            hashtags += " #DataBreach"
        elif 'vulnerability' in tweet_content.lower() or 'cve' in tweet_content.lower():
            hashtags += " #InfoSec"
        elif 'malware' in tweet_content.lower() or 'virus' in tweet_content.lower():
            hashtags += " #Malware"
        
        # Combine content with hashtags and URL
        max_length = 280 - len(news['link']) - len(hashtags) - 4  # 4 chars for newlines
        if len(tweet_content) > max_length:
            tweet_content = tweet_content[:max_length-3] + "..."
        
        final_tweet = f"{tweet_content}\n{hashtags}\n{news['link']}"
        
        logger.info(f"Generated tweet content: {final_tweet}")
        return final_tweet

    except Exception as e:
        logger.error(f"Error generating tweet content: {str(e)}")
        raise

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def post_tweet():
    """Generate and post a tweet with retry logic."""
    try:
        # Get Twitter client
        twitter = get_twitter_client()
        
        # Generate tweet content
        tweet_content = generate_tweet_content()
        
        # Check if we have content to tweet
        if not tweet_content:
            logger.warning("No tweet content generated, skipping post")
            return None
            
        logger.info(f"Generated tweet: {tweet_content}")
        
        # Add small delay before posting
        time.sleep(2)
        
        # Post tweet
        response = twitter.create_tweet(text=tweet_content)
        tweet_id = response.data['id']
        logger.info(f"Successfully posted tweet with ID: {tweet_id}")
        
        return tweet_id
        
    except Exception as e:
        logger.error(f"Error posting tweet: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        logger.info("Starting tweet bot...")
        
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
    except Exception as e:
        logger.error(f"Tweet bot failed: {str(e)}")
        raise 