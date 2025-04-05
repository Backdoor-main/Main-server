# Setting Up Dropbox OAuth for Your Render Deployment

This guide explains how to set up Dropbox OAuth for your application deployed on Render.com.

## Redirect URL Setup

When you deploy your application on Render.com, you need to add a redirect URL to your Dropbox app settings.

### Your Redirect URL

```
https://YOUR_SERVICE_NAME.onrender.com/oauth/dropbox/callback
```

Replace `YOUR_SERVICE_NAME` with your actual Render service name.

### Steps to Add the Redirect URL

1. Go to the [Dropbox Developer Console](https://www.dropbox.com/developers/apps)
2. Select your app (the one with app key: `2bi422xpd3xd962`)
3. In the app's settings page, find the "OAuth 2" section
4. Look for "Redirect URIs" - this is where you need to add the redirect URL
5. Click "Add" or "Edit" and enter your URL from above
6. Save your changes

## Using OAuth with Your Application

Your application has built-in OAuth routes that make it easy to authenticate with Dropbox.

### Authorization URL

To start the OAuth flow, visit:

```
https://YOUR_SERVICE_NAME.onrender.com/oauth/dropbox/authorize
```

This URL will redirect you to Dropbox to authorize your application. After authorization, Dropbox will redirect back to your application's callback URL, which will automatically handle the token exchange.

### Checking OAuth Status

To check the status of your OAuth tokens, visit:

```
https://YOUR_SERVICE_NAME.onrender.com/oauth/dropbox/status
```

This endpoint will show you:
- Whether you have valid tokens
- When your access token expires
- The redirect URI being used
- A link to start the authorization process

## Automatic Token Refresh

Once you've set up OAuth using the steps above, your application will automatically refresh the access token when it expires, as long as you have a valid refresh token.

## Environment Variables

Make sure your Render deployment has these environment variables set:

- `DROPBOX_APP_KEY` - Your Dropbox app key
- `DROPBOX_APP_SECRET` - Your Dropbox app secret
- `RENDER_SERVICE_NAME` - Your Render service name (optional, but recommended)

## Troubleshooting

If you encounter issues:

1. Check your Dropbox app settings to make sure the redirect URL is configured correctly
2. Ensure your app has the required permissions (files.content.read, files.content.write)
3. Verify that your environment variables are set correctly in Render
4. Check the application logs for any error messages related to OAuth

If authentication fails, the application will automatically fall back to local storage.
