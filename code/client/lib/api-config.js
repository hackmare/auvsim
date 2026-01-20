/**
 * AUV Sim API Configuration
 * Centralized configuration for API connectivity
 */

const APIConfig = {
  // Server hostname
  hostname: 'localhost',

  // Server port
  port: 8080,

  // Protocol (http or https)
  protocol: 'http',

  // Get the full base URL
  get baseUrl() {
    return `${this.protocol}://${this.hostname}:${this.port}`;
  },

  // API Endpoints
  endpoints: {
    status: '/status',
    pitch: '/pitch',
    yaw: '/yaw',
    prop: '/prop',
  },

  // Get full endpoint URL
  getEndpointUrl(endpoint) {
    if (this.endpoints[endpoint]) {
      return `${this.baseUrl}${this.endpoints[endpoint]}`;
    }
    throw new Error(`Unknown endpoint: ${endpoint}`);
  },

  // Request configuration
  requestConfig: {
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: 5000, // 5 seconds
  },

  // Polling interval for status updates (ms)
  statusPollInterval: 100,

  // Maximum retries for failed requests
  maxRetries: 3,

  // Retry delay (ms)
  retryDelay: 500,

  // Validate configuration
  validate() {
    if (!this.hostname) throw new Error('Hostname not configured');
    if (!this.port) throw new Error('Port not configured');
    if (!this.protocol) throw new Error('Protocol not configured');
    return true;
  },
};

// Log configuration on load (development helper)
if (typeof console !== 'undefined') {
  console.log('AUV API Config:', {
    baseUrl: APIConfig.baseUrl,
    statusPollInterval: APIConfig.statusPollInterval,
    requestTimeout: APIConfig.requestConfig.timeout,
  });
}

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = APIConfig;
}
