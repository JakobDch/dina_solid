import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../api/apiClient';

export interface HealthStatus {
  status: 'healthy' | 'starting' | 'error';
  ready: boolean;
  services: {
    embedding_model: {
      ready: boolean;
      status: any;
    };
    database: {
      ready: boolean;
    };
    graphdb: {
      ready: boolean;
    };
  };
}

export interface UseBackendHealthResult {
  isHealthy: boolean;
  isLoading: boolean;
  error: string | null;
  healthStatus: HealthStatus | null;
  retryCount: number;
  lastChecked: Date | null;
  checkHealth: () => Promise<void>;
}

interface UseBackendHealthOptions {
  pollInterval?: number;
  maxRetries?: number;
  retryDelay?: number;
  autoStart?: boolean;
}

export function useBackendHealth(options: UseBackendHealthOptions = {}): UseBackendHealthResult {
  const { t } = useTranslation();
  const {
    pollInterval = 8000, // 8 seconds - even more relaxed
    maxRetries = 30, // 120 seconds total with 8s intervals
    autoStart = true
  } = options;

  const [isHealthy, setIsHealthy] = useState(false);
  const [isLoading, setIsLoading] = useState(autoStart);
  const [error, setError] = useState<string | null>(null);
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const checkHealth = useCallback(async (): Promise<void> => {
    try {
      setError(null);
      const response = await api.get<HealthStatus>('/api/v1/health');
      const health = response.data;
      
      console.log('Health check response:', health); // Debug log
      
      setHealthStatus(health);
      setLastChecked(new Date());
      
      if (health.ready) {
        console.log('Backend is ready, setting isHealthy to true'); // Debug log
        setIsHealthy(true);
        setIsLoading(false);
        setRetryCount(0);
      } else {
        console.log('Backend not ready, continuing to poll'); // Debug log
        // Backend is starting up, continue polling
        setIsHealthy(false);
        setRetryCount(prev => {
          if (prev >= maxRetries) {
            setError(t('errors.backendSlowStart'));
            setIsLoading(false);
            return prev;
          }
          return prev + 1;
        });
      }
    } catch (err: any) {
      console.log('Health check error:', err); // Debug log
      setLastChecked(new Date());
      
      setRetryCount(prev => {
        if (prev >= maxRetries) {
          setError(err.response?.data?.message || err.message || t('errors.backendUnavailable'));
          setIsHealthy(false);
          setIsLoading(false);
          return prev;
        }
        return prev + 1;
      });
    }
  }, [maxRetries, t]);

  // Start health checking
  const startHealthCheck = useCallback(() => {
    console.log('Starting health check'); // Debug log
    setIsLoading(true);
    setRetryCount(0);
    setError(null);
    setIsHealthy(false);
    checkHealth();
  }, [checkHealth]);

  // Polling effect - only start polling when needed
  useEffect(() => {
    if (isHealthy || error) {
      console.log('Stopping polling - isHealthy:', isHealthy, 'error:', error); // Debug log
      return;
    }

    if (isLoading && retryCount < maxRetries) {
      console.log('Setting up polling interval, retryCount:', retryCount); // Debug log
      const interval = setInterval(checkHealth, pollInterval);
      return () => {
        console.log('Clearing polling interval'); // Debug log
        clearInterval(interval);
      };
    }
  }, [isHealthy, isLoading, error, retryCount, maxRetries, pollInterval, checkHealth]);

  // Auto-start effect - simplified
  useEffect(() => {
    if (autoStart && !isHealthy && !error) {
      console.log('Auto-starting health check'); // Debug log
      startHealthCheck();
    }
  }, [autoStart]); // Only depend on autoStart to avoid loops

  return {
    isHealthy,
    isLoading,
    error,
    healthStatus,
    retryCount,
    lastChecked,
    checkHealth: async () => { startHealthCheck(); }
  };
}