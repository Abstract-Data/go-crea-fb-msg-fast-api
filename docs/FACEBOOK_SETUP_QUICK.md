# Facebook Setup Quick Reference

## Get Your Credentials

### 1. Create Facebook App (5 min)

1. Go to https://developers.facebook.com/apps
2. Click "Create App" → Choose "Business"
3. Name: "Your Bot Name"
4. Complete security check

### 2. Add Messenger (2 min)

1. In app dashboard → "Add Products" → "Messenger"
2. Click "Set Up"

### 3. Get Page Access Token (3 min)

1. Messenger Settings → "Access Tokens"
2. Click "Add or Remove Pages"
3. Select your page → Grant permissions
4. Click "Generate Token"
5. **Copy immediately!** (Starts with EAAA...)

### 4. Find Page ID (1 min)

- Look in the page dropdown in Access Tokens
- Format: 15-digit number like `123456789012345`

### 5. Create Verify Token (1 min)

- Use: `openssl rand -base64 32`
- Or create your own: `my-bot-verify-2024`
- **Save it** — you need this for webhook setup!

## Run CLI Setup

```bash
uv run python -m src.cli.setup_cli setup
```

Paste when prompted:

- Website URL
- Page ID (15 digits)
- Page Access Token (EAAA...)
- Verify Token (your choice, or press Enter for random)

Type `?` at any credential prompt for detailed help on where to find it.

## Deploy and Configure Webhook

After deploying to Railway:

1. Get Railway URL: `https://your-app.railway.app`
2. Facebook App → Messenger → Webhooks
3. Add Callback URL: `https://your-app.railway.app/webhook`
4. Enter Verify Token (same as CLI setup)
5. Subscribe to: `messages`
6. Subscribe your page

## Troubleshooting

**Token invalid?**

- Regenerate in Messenger Settings
- Copy the entire token (starts with EAAA, 100+ characters)

**Webhook verification failed?**

- Check verify token matches exactly what you entered in CLI
- Ensure app is deployed and running
- Test: `https://your-app.railway.app/health`

**Messages not arriving?**

- Page subscribed to webhook?
- "messages" subscription checked?
- Check Railway logs: `railway logs`

For more operational issues, see [RUNBOOK.md](../RUNBOOK.md).
