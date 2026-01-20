/**
 * AUV Sim API Client
 * Handles all communication with the backend API
 */

class AUVSimClient {
  constructor(config = APIConfig) {
    this.config = config;
    this.config.validate();
    this.lastStatus = null;
    this.retryCount = {};
  }

  /**
   * Make a generic HTTP request with retry logic
   */
  async request(method, endpoint, body = null, retryAttempt = 0) {
    const url = this.config.getEndpointUrl(endpoint);
    const options = {
      method,
      headers: this.config.requestConfig.headers,
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(
        () => controller.abort(),
        this.config.requestConfig.timeout
      );

      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(
          `HTTP ${response.status}: ${response.statusText}`
        );
      }

      return await response.json();
    } catch (error) {
      if (retryAttempt < this.config.maxRetries) {
        console.warn(
          `Request failed (attempt ${retryAttempt + 1}/${this.config.maxRetries}):`,
          error.message
        );
        await this.sleep(this.config.retryDelay);
        return this.request(method, endpoint, body, retryAttempt + 1);
      }

      throw error;
    }
  }

  /**
   * Get current vehicle status
   */
  async getStatus() {
    this.lastStatus = await this.request('GET', 'status');
    return this.lastStatus;
  }

  /**
   * Set pitch fin value (-30 to 30)
   */
  async setPitch(value) {
    if (typeof value !== 'number' || value < -50 || value > 50) {
      throw new Error('Pitch value must be a number between -50 and 50');
    }
    return await this.request('POST', 'pitch', { value });
  }

  /**
   * Set yaw fin value (-30 to 30)
   */
  async setYaw(value) {
    if (typeof value !== 'number' || value < -50 || value > 50) {
      throw new Error('Yaw value must be a number between -50 and 50');
    }
    return await this.request('POST', 'yaw', { value });
  }

  /**
   * Set propeller value (-30 to 100)
   */
  async setProp(value) {
    if (typeof value !== 'number' || value < -50 || value > 150) {
      throw new Error('Prop value must be a number between -50 and 150');
    }
    return await this.request('POST', 'prop', { value });
  }

  /**
   * Start polling for status updates
   */
  startStatusPolling(callback) {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
    }

    const poll = async () => {
      try {
        const status = await this.getStatus();
        callback(null, status);
      } catch (error) {
        callback(error, null);
      }
    };

    // Poll immediately, then at interval
    poll();
    this.pollingInterval = setInterval(
      poll,
      this.config.statusPollInterval
    );
  }

  /**
   * Stop polling for status updates
   */
  stopStatusPolling() {
    if (this.pollingInterval) {
      clearInterval(this.pollingInterval);
      this.pollingInterval = null;
    }
  }

  /**
   * Utility sleep function
   */
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Check if client is connected and API is healthy
   */
  async healthCheck() {
    try {
      const status = await this.getStatus();
      return {
        connected: true,
        status,
      };
    } catch (error) {
      return {
        connected: false,
        error: error.message,
      };
    }
  }
}

// Create a singleton instance
const auvClient = new AUVSimClient(APIConfig);

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { AUVSimClient, auvClient };
}
