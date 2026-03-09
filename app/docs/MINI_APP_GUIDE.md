# 🎯 Telegram Mini App Setup Guide

This guide will help you set up a Telegram Mini App for your Football Betting Analysis bot.

## 📋 What is a Telegram Mini App?

A Telegram Mini App is a web application that runs directly within the Telegram interface, providing users with a rich, interactive experience without leaving the app. It's perfect for displaying complex data like betting opportunities in an organized, user-friendly way.

## 🚀 Features Implemented

### ✅ Bot Integration
- **New `/bettings` command** - Opens the Mini App directly
- **Updated `/start` command** - Now includes a "🎯 Betting Opportunities" button
- **Updated `/help` command** - Documents the new Mini App functionality

### ✅ Web Interface
- **Responsive design** - Works on mobile and desktop
- **Telegram theme integration** - Matches user's Telegram theme
- **Real-time data** - Fetches live betting opportunities from your database
- **Interactive interface** - Clean, modern UI with confidence scores and match details

### ✅ API Endpoints
- **GET `/football/api/v1/mini-app/`** - Serves the Mini App HTML interface
- **GET `/football/api/v1/mini-app/betting-opportunities`** - API endpoint for betting opportunities data

## 🛠️ Setup Instructions

### 1. Configure Your Telegram Bot

1. Go to [@BotFather](https://t.me/botfather) on Telegram
2. Send `/mybots`
3. Select your bot
4. Choose **"Bot Settings"** → **"Menu Button"**
5. Set the Web App URL to: `https://your-domain.com/football/api/v1/mini-app/`

### 2. Environment Configuration

Make sure your `BASE_HOST` environment variable is set to your public URL:

```bash
export BASE_HOST='https://your-domain.com'
```

Or add it to your `.env` file:
```
BASE_HOST=https://your-domain.com
```

### 3. Start Your Application

```bash
# Development
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Production (with gunicorn)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 4. Test the Mini App

1. Send `/start` to your bot
2. Click the **"🎯 Betting Opportunities"** button
3. Or use the `/bettings` command directly

## 📱 User Experience

### For Users:
1. **Easy Access** - Click a button to open the Mini App
2. **Rich Interface** - See betting opportunities with:
   - Match details (teams, league, date)
   - Confidence scores (as percentages)
   - Rule information
   - Live/scheduled status
3. **Real-time Updates** - Refresh button to get latest opportunities
4. **Mobile Optimized** - Perfect for mobile Telegram users

### For Developers:
- **Modular Design** - Easy to extend with new features
- **API-First** - Clean separation between frontend and backend
- **Responsive** - Works on all device sizes
- **Theme Aware** - Automatically adapts to Telegram themes

## 🔧 Technical Details

### File Structure
```
app/
├── api/
│   └── mini_app_routes.py      # Mini App API endpoints
├── bot/
│   └── handlers.py            # Updated with Mini App buttons
└── main.py                    # Updated with Mini App routes

setup_mini_app.py              # Setup helper script
MINI_APP_GUIDE.md             # This documentation
```

### Key Components

1. **Mini App Routes** (`app/api/mini_app_routes.py`):
   - Serves HTML interface
   - Provides betting opportunities API
   - Handles CORS and error responses

2. **Bot Integration** (`app/bot/handlers.py`):
   - New `/bettings` command
   - Updated start message with Mini App button
   - WebAppInfo integration

3. **HTML Interface**:
   - Telegram WebApp.js integration
   - Theme-aware styling
   - Responsive design
   - Real-time data fetching

## 🎨 Customization

### Styling
The Mini App uses CSS custom properties that automatically adapt to Telegram themes:
- `--tg-theme-bg-color` - Background color
- `--tg-theme-text-color` - Text color
- `--tg-theme-button-color` - Button color
- `--tg-theme-hint-color` - Hint/secondary text color

### Adding Features
To add new features to the Mini App:

1. **Add API endpoints** in `app/api/mini_app_routes.py`
2. **Update the HTML interface** with new UI elements
3. **Add JavaScript functions** for new functionality
4. **Test on different devices** and Telegram clients

## 🐛 Troubleshooting

### Common Issues:

1. **Mini App not opening**:
   - Check that your server is accessible from the internet
   - Verify the BASE_HOST environment variable
   - Ensure HTTPS is used in production

2. **Data not loading**:
   - Check database connection
   - Verify API endpoints are working
   - Check browser console for JavaScript errors

3. **Styling issues**:
   - Ensure Telegram WebApp.js is loaded
   - Check CSS custom properties
   - Test on different devices

### Debug Mode:
Add `console.log()` statements in the JavaScript to debug issues:
```javascript
console.log('Telegram WebApp:', window.Telegram.WebApp);
console.log('Theme params:', window.Telegram.WebApp.themeParams);
```

## 🚀 Next Steps

### Potential Enhancements:
1. **User Authentication** - Track user preferences
2. **Filtering Options** - Filter by league, confidence, etc.
3. **Detailed Views** - Click to see more match details
4. **Push Notifications** - Real-time updates within the Mini App
5. **Analytics** - Track user interactions
6. **Favorites** - Let users save interesting opportunities

### Production Considerations:
1. **HTTPS Required** - Telegram requires HTTPS for Mini Apps
2. **Performance** - Optimize for mobile devices
3. **Caching** - Consider caching for better performance
4. **Monitoring** - Set up logging and error tracking

## 📞 Support

If you encounter any issues:
1. Check the logs for error messages
2. Test the API endpoints directly
3. Verify your Telegram bot configuration
4. Ensure your server is accessible from the internet

---

**🎉 Congratulations!** You now have a fully functional Telegram Mini App for your Football Betting Analysis bot!
