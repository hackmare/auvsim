# AUV Sim - Localhost Demo Setup

This directory contains the web UI for the AUV Simulator with a clean separation of API configuration and client libraries.

## Project Structure

```
client/
├── ux.html              # Main HTML UI
├── lib/
│   ├── api-config.js    # API configuration (hostname, port, endpoints)
│   └── auv-client.js    # API client library for server communication
└── README.md            # This file
```

## Quick Start

### Prerequisites
- Python 3.11+ with the AUV simulator running
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Running the Demo

1. **Start the AUV simulator backend** (in the service directory):
```bash
cd /Users/morgane/github/auvsim/code/service
python auv_sim_api.py
```

This will start the API on `http://localhost:8080` with full WAF protection enabled.

2. **Open the UI** in your browser:
```
http://localhost:5000/ux.html
```

Or simply open `ux.html` directly in your browser if serving locally.

## API Configuration

The API configuration is defined in `lib/api-config.js` and can be easily customized:

```javascript
const APIConfig = {
  hostname: 'localhost',  // Change to your server hostname
  port: 8080,            // Change to your server port
  protocol: 'http',      // Use 'https' for production
  // ... more settings
};
```

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `hostname` | `localhost` | Server hostname or IP address |
| `port` | `8080` | Server port |
| `protocol` | `http` | Protocol (http or https) |
| `statusPollInterval` | `100` | Status update frequency (ms) |
| `requestConfig.timeout` | `5000` | Request timeout (ms) |
| `maxRetries` | `3` | Automatic retry attempts for failed requests |
| `retryDelay` | `500` | Delay between retries (ms) |

## API Client

The `lib/auv-client.js` library provides a clean interface to the backend:

### Methods

```javascript
// Get current vehicle status
await auvClient.getStatus()

// Set pitch fin (-30 to 30 degrees)
await auvClient.setPitch(15)

// Set yaw fin (-30 to 30 degrees)
await auvClient.setYaw(-10)

// Set propeller (-30 to 100 percent)
await auvClient.setProp(50)

// Start polling for status updates every poll interval
auvClient.startStatusPolling((error, status) => {
  if (error) console.error(error);
  else console.log(status);
})

// Stop polling
auvClient.stopStatusPolling()

// Check API health
const health = await auvClient.healthCheck()
```

## Backend API Endpoints

The backend provides the following endpoints (all on `localhost:8080` by default):

| Endpoint | Method | Description | Payload |
|----------|--------|-------------|---------|
| `/status` | GET | Get vehicle state and telemetry | N/A |
| `/pitch` | POST | Set horizontal fin angle | `{"value": -30..30}` |
| `/yaw` | POST | Set vertical fin angle | `{"value": -30..30}` |
| `/prop` | POST | Set propeller throttle | `{"value": -30..100}` |

## Backend Security Features

The backend (`auv_sim_api.py`) includes production-grade WAF protection:

- **Rate Limiting**: 300 requests per minute per IP, automatic 5-minute IP blocking
- **Input Validation**: SQL injection, XSS, path traversal, and command injection detection
- **Request Filtering**: Suspicious User-Agent blocking, forbidden header detection, request size limits
- **Security Headers**: HSTS, CSP, X-Frame-Options, X-XSS-Protection, and more
- **Audit Logging**: All requests and security events logged for forensics

## Customization

### Changing the Server Address

To point the UI to a different server, edit `lib/api-config.js`:

```javascript
const APIConfig = {
  hostname: 'your-server.com',  // Your server
  port: 8080,                    // Your port
  protocol: 'https',             // Use https if required
  // ... rest of config
};
```

### Extending the Client

Add custom methods to `lib/auv-client.js`:

```javascript
class AUVSimClient {
  // ... existing methods
  
  async customCommand(param) {
    return await this.request('POST', 'custom-endpoint', { param });
  }
}
```

## Development Notes

- The client automatically retries failed requests with exponential backoff
- All network errors are caught and displayed in the UI's status indicators
- Configuration and client are loaded before the main UI script for early availability
- The UI maintains responsive connection status via the colored status dots

## Troubleshooting

### "Too many requests" error
- The backend rate limiter may have blocked your IP
- Default limit is 300 requests/minute per IP
- Wait 5 minutes for automatic unblock, or restart the backend

### Connection errors
- Verify the backend is running: `python auv_sim_api.py`
- Check the hostname and port in `api-config.js`
- Ensure firewall allows connections to port 8080

### Slow response
- Increase `statusPollInterval` in `api-config.js` if polling is too aggressive
- Check network latency to server
- Monitor backend logs for WAF issues

## License

This project is licensed under the PolyForm Noncommercial License 1.0.0.
See LICENSE.md and COMMERCIAL.md for details.
