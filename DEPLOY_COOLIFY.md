# Deployment Guide for Coolify

## Prerequisites

1. Supabase PostgreSQL database
2. Telegram bot token and group IDs
3. Coolify instance

## Environment Variables

Set these in Coolify's environment variables section:

### Required Variables

```env
# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_GROUP_ID=-1234567890  # Your general news group ID
TELEGRAM_VULNERABILITIES_GROUP_ID=-1234567891  # Your vulnerabilities group ID

# Database (Supabase)
# IMPORTANT: Use the pooler endpoint (port 6543) for better stability
DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT_ID]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres

# Force IPv4 connections (set to true if having IPv6 connection issues)
FORCE_IPV4=true

# Environment
ENVIRONMENT=production
```

### Optional Variables

```env
# Topics (if using forum supergroups)
TELEGRAM_TOPIC_ID=
TELEGRAM_VULNERABILITIES_TOPIC_ID=

# Translation
MICROSOFT_TRANSLATOR_KEY=
OPENAI_API_KEY=

# Monitoring
SENTRY_DSN=
PARSE_API_KEY=your_secure_api_key

# Proxy (if needed)
PROXY_URL=
PROXY_USERNAME=
PROXY_PASSWORD=
```

## Coolify Configuration

### 1. Application Settings

- **Build Pack**: Nixpacks (auto-detected as Python)
- **Port**: 8000 (for health checks and metrics)
- **Health Check Path**: `/health`

### 2. Health Check Configuration

In Coolify, set:
- **Health Check Enabled**: Yes
- **Health Check Path**: `/health`
- **Health Check Port**: 8000
- **Health Check Interval**: 30 seconds

### 3. Resource Limits (Recommended)

- **Memory**: 512MB minimum
- **CPU**: 0.5 cores minimum

## Deployment Steps

1. **Fork/Clone Repository**
   ```bash
   git clone https://github.com/caesarclown9/MegaCyberBot.git
   ```

2. **Set Environment Variables in Coolify**
   - Go to your application settings
   - Add all required environment variables
   - Save configuration

3. **Deploy**
   - Coolify will automatically detect Python application
   - Build will use Nixpacks
   - Container will start with health checks

## Monitoring

### Health Check Endpoints

The bot exposes several endpoints for monitoring:

- `GET /health` - Basic health check
- `GET /metrics` - Prometheus metrics
- `GET /status` - Detailed status information
- `GET /ping` - Simple ping endpoint

### Logs

Check logs in Coolify's log viewer. Look for:
- `[STARTUP]` - Initialization messages
- `[HEARTBEAT]` - Periodic health checks
- `[ERROR]` - Error messages

## Troubleshooting

### ⚠️ IMPORTANT: Setting DATABASE_URL in Coolify

**Common Issue**: Make sure to set DATABASE_URL correctly in Coolify:
- ✅ CORRECT: Just paste the URL value: `postgresql+asyncpg://postgres...`
- ❌ WRONG: Including the variable name: `DATABASE_URL=postgresql+asyncpg://postgres...`
- ❌ WRONG: Extra spaces in URL

### Database Connection Issues

1. **IMPORTANT - Use Pooler Endpoint** (REQUIRED for Coolify):
   ```
   # Pooler endpoint (port 6543) - REQUIRED for stability
   DATABASE_URL=postgresql+asyncpg://postgres.[PROJECT_ID]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
   ```
   
   ⚠️ **DO NOT use direct connection (port 5432) - it causes IPv6 issues on Coolify!**
   
   **"Tenant or user not found" Error:**
   If you see this error, check:
   - Username format must be `postgres.[project-ref]` (get from Supabase dashboard)
   - Password is correct and doesn't contain special characters that need escaping
   - You're using the pooler endpoint (port 6543), not direct connection
   - No spaces in the DATABASE_URL value

2. **IPv6 Connection Issues** (if still occurring):
   - If you see `OSError: [Errno 101] Connect call failed` with IPv6 address like `2a05:d016:...`
   - Add environment variable: `FORCE_IPV4=true`
   - The bot will automatically force IPv4 connections

3. **Get Correct Connection String from Supabase**:
   - Go to Supabase Dashboard → Settings → Database
   - Click on "Connection pooling" tab (NOT "Connection string")
   - Copy the "Connection string" from pooler section
   - Replace `postgresql://` with `postgresql+asyncpg://`

4. **Check Supabase Settings**:
   - Go to Supabase Dashboard → Settings → Database
   - Ensure "Allow connections from all IPs" is enabled (or add Coolify's IP)
   - Use connection string from "Connection pooling" section

5. **Common Error Messages**:
   ```
   [STARTUP] Database connection attempt X/3 failed
   OSError: [Errno 101] Connect call failed  # IPv6 issue
   password authentication failed  # Wrong password
   timeout  # Network or firewall issue
   ```

### Bot Not Starting

1. Verify TELEGRAM_BOT_TOKEN is correct
2. Check group IDs are negative numbers
3. Run debug script locally:
   ```bash
   python debug_startup.py
   ```

### Health Check Failing

1. Check if port 8000 is exposed
2. Verify metrics are enabled (ENABLE_METRICS=true)
3. Check application logs for API server startup

### Common Issues

| Issue | Solution |
|-------|----------|
| Container keeps restarting | Check environment variables, especially DATABASE_URL |
| No messages sent | Verify group IDs and bot permissions |
| Database migrations fail | Check DATABASE_URL and network connectivity |
| Health check timeout | Increase start_period in health check settings |

## Support

For issues specific to the bot, check:
- Application logs in Coolify
- Database connection in Supabase
- Bot permissions in Telegram groups

## Security Notes

1. Never commit `.env` file to repository
2. Use strong database passwords
3. Rotate PARSE_API_KEY regularly
4. Keep bot token secret