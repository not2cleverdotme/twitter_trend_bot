# Cybersecurity Twitter Bot

An automated Twitter bot that posts cybersecurity-related content every 4 hours using AI-generated content.

## Features

- Posts every 4 hours automatically using GitHub Actions
- Generates cybersecurity-focused content using GPT-3.5
- Topics include:
  - Recent cybersecurity threats
  - Security best practices
  - Privacy tips
  - Data protection
  - Network security

## Setup

1. Create a Twitter Developer Account:
   - Go to [Twitter Developer Portal](https://developer.twitter.com/)
   - Create a new Project and App
   - Generate API Keys and Access Tokens
   - Ensure your App has Read and Write permissions

2. Get an OpenAI API Key:
   - Go to [OpenAI Platform](https://platform.openai.com/)
   - Create an account or sign in
   - Generate an API key

3. Configure GitHub Repository:
   - Fork or clone this repository
   - Go to Settings > Secrets and Variables > Actions
   - Add the following secrets:
     ```
     TWITTER_API_KEY
     TWITTER_API_SECRET
     TWITTER_ACCESS_TOKEN
     TWITTER_ACCESS_TOKEN_SECRET
     OPENAI_API_KEY
     ```

4. Enable GitHub Actions:
   - Go to Actions tab
   - Enable workflows
   - The bot will automatically start posting every 4 hours

## Local Testing

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set environment variables:
```bash
export TWITTER_API_KEY=your_api_key
export TWITTER_API_SECRET=your_api_secret
export TWITTER_ACCESS_TOKEN=your_access_token
export TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
export OPENAI_API_KEY=your_openai_api_key
```

3. Run the bot:
```bash
python tweet_bot.py
```

## Customization

To modify the tweet content or frequency:

1. Edit the prompt in `tweet_bot.py` to change content focus
2. Modify the cron schedule in `.github/workflows/tweet.yml` to change frequency

## Rate Limits

- Twitter API v2 (Free Tier): 500 tweets per month
- OpenAI API: Depends on your plan

## Troubleshooting

Common issues:
1. Rate limit exceeded
2. Invalid credentials
3. Network errors

Check the GitHub Actions logs for detailed error messages. 