import { Typography, Button } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import type { HealthStatus } from '../hooks/useBackendHealth';

const { Text } = Typography;

interface AppLoadingScreenProps {
  isLoading: boolean;
  error: string | null;
  healthStatus: HealthStatus | null;
  retryCount: number;
  maxRetries: number;
  onRetry: () => void;
}

export default function AppLoadingScreen({
  isLoading,
  error,
  onRetry
}: AppLoadingScreenProps) {

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      background: '#ffffff'
    }}>
      {/* Loading State with Video Animation */}
      {isLoading && !error && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '24px'
        }}>
          {/* Video Loading Animation */}
          <div style={{
            width: '200px',
            height: '200px',
            borderRadius: '50%',
            overflow: 'hidden',
            flexShrink: 0
          }}>
            <video
              autoPlay
              loop
              muted
              playsInline
              ref={(el) => { if (el) el.playbackRate = 2.0; }}
              style={{
                width: '110%',
                height: '110%',
                marginLeft: '-5%',
                marginTop: '-5%',
                objectFit: 'cover'
              }}
            >
              <source src="/dina_loading.mp4" type="video/mp4" />
            </video>
          </div>

          <Text style={{
            color: '#64748b',
            fontSize: '15px',
            fontWeight: 400
          }}>
            Wird geladen...
          </Text>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '16px',
          maxWidth: '320px',
          textAlign: 'center'
        }}>
          <Text style={{
            color: '#64748b',
            fontSize: '15px'
          }}>
            Verbindung fehlgeschlagen
          </Text>

          <Button
            type="primary"
            icon={<ReloadOutlined />}
            onClick={onRetry}
            style={{
              background: '#C6712F',
              border: 'none',
              borderRadius: '8px',
              fontWeight: 600,
              height: '44px',
              padding: '0 24px'
            }}
          >
            Erneut versuchen
          </Button>
        </div>
      )}
    </div>
  );
}
