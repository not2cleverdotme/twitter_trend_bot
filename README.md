# Cybersecurity News Twitter Bot 🚨

An automated Twitter bot that posts the latest cybersecurity news from reputable sources. The bot fetches news from multiple cybersecurity news feeds, uses OpenAI to create concise summaries, and posts them to Twitter.

## Features

- 🔄 Fetches news from multiple reputable cybersecurity sources:
  - BleepingComputer
  - Dark Reading
  - CyberScoop

- 🎲 Random Selection:
  - Randomly selects articles from the past 12 hours
  - Ensures variety in sources and content
  - Falls back to most recent if no articles in the 12-hour window

- 🤖 Smart Summarization:
  - Uses OpenAI GPT-3.5 to create concise, informative summaries
  - Maintains the original context and key points
  - Automatically adds relevant hashtags based on content

- ⏱️ Automated Posting:
  - Posts every 6 hours via GitHub Actions
  - Includes source links for further reading
  - Handles rate limiting and retries

## Setup

### Prerequisites

- Python 3.10 or higher
- Twitter Developer Account with Elevated access
- OpenAI API key

### Required Environment Variables

```
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_SECRET=your_twitter_api_secret
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret
OPENAI_API_KEY=your_openai_api_key
```

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/twitter_trend_bot.git
cd twitter_trend_bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up GitHub repository secrets:
   - Go to your repository's Settings > Secrets
   - Add all the required environment variables listed above

### Running Locally

To run the bot locally:

```bash
python tweet_bot.py
```

## GitHub Actions Workflow

The bot runs automatically every 4 hours using GitHub Actions. The workflow:
- Runs on Ubuntu latest
- Uses Python 3.10
- Installs dependencies
- Executes the bot
- Handles any errors

## Tweet Format

Each tweet includes:
1. 🚨 Attention-grabbing headline
2. Key findings or impact
3. Relevant hashtags (#CyberSecurity, #InfoSec, etc.)
4. Source URL for further reading

## Error Handling

The bot includes:
- Retry logic for API calls
- Feed parsing error handling
- Rate limiting management
- Detailed logging
- Fallback mechanisms

## Dependencies

- tweepy: Twitter API client
- openai: OpenAI GPT-3.5 integration
- feedparser: RSS feed parsing
- tenacity: Retry logic
- requests: HTTP client

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to BleepingComputer, Dark Reading, and CyberScoop for their RSS feeds
- Built with OpenAI's GPT-3.5 for content summarization
- Powered by Twitter's API v2 
