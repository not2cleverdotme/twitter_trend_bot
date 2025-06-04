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
                'url': 'https://feeds.feedburner.com/TheHackerNews',
                'name': 'The Hacker News'
            },
            {
                'url': 'https://www.bleepingcomputer.com/feed',
                'name': 'BleepingComputer'
            },
            {
                'url': 'https://darkreading.com/rss.xml',
                'name': 'Dark Reading'
            },
            {
                'url': 'https://www.cyberscoop.com/feed',
                'name': 'CyberScoop'
            }
        ]

        # Get current time for age comparison
        current_time = datetime.utcnow()
        all_entries = []

        for feed_info in feeds:
            try:
                logger.info(f"Fetching feed from {feed_info['name']}...")
                feed = feedparser.parse(feed_info['url'])
                
                if feed.status == 200:
                    # Process each entry in the feed
                    for entry in feed.entries[:5]:  # Look at top 5 entries from each feed
                        try:
                            # Get publication date
                            if hasattr(entry, 'published_parsed'):
                                pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                            elif hasattr(entry, 'updated_parsed'):
                                pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                            else:
                                continue

                            # Only include entries from the last 24 hours
                            age = current_time - pub_date
                            if age <= timedelta(days=1):
                                # Clean and format the entry
                                title = entry.title.strip()
                                description = entry.get('description', '')
                                if hasattr(entry, 'summary'):
                                    description = entry.summary
                                
                                # Remove HTML tags from description
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
                else:
                    logger.warning(f"Failed to fetch {feed_info['name']}: Status {feed.status}")
            
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
    """Generate cybersecurity-related tweet content using OpenAI with retry logic."""
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
        
        if news:
            logger.info(f"Generating tweet for news from {news['source']}")
            
            prompt = f"""Create an engaging cybersecurity news tweet about this:

Article: {news['title']}
Source: {news['source']}
Details: {news['description']}

Requirements:
1. Start with 🚨 and a compelling hook
2. Highlight key security impact or takeaway
3. End with #CyberSecurity
4. Keep it under 250 characters (we'll add the URL)
5. Make it informative and engaging

Example format:
🚨 [Compelling hook]: Key finding
Important impact or action item
#CyberSecurity"""

        else:
            logger.info("No recent news found, using default cybersecurity topics")
            prompt = """Generate an engaging cybersecurity tweet about one of these current topics:
            - Zero-day vulnerabilities
            - Ransomware prevention
            - Multi-factor authentication
            - Social engineering threats
            - Password security best practices
            
            Format:
            🚨 Start with an attention-grabbing fact or tip
            Add a brief, practical explanation
            End with #CyberSecurity
            
            Keep it under 280 characters and make it conversational."""

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a cybersecurity expert who creates engaging, informative security alerts. Your style is clear, authoritative, and actionable."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7,
            request_timeout=30
        )
        
        tweet_content = response.choices[0].message['content'].strip()
        
        # If we have news, append the source URL
        if news:
            # Ensure we have room for the URL
            max_length = 280 - len(news['link']) - 2  # 2 chars for newline
            if len(tweet_content) > max_length:
                tweet_content = tweet_content[:max_length-3] + "..."
            tweet_content = f"{tweet_content}\n{news['link']}"
        
        # Final length check
        if len(tweet_content) > 280:
            tweet_content = tweet_content[:277] + "..."
        
        logger.info(f"Generated tweet content: {tweet_content}")
        return tweet_content

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