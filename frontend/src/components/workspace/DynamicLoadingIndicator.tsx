import { useTheme } from '../../contexts/ThemeContext';
import type { CurrentStepInfo } from '../../types';

interface DynamicLoadingIndicatorProps {
  currentStep?: CurrentStepInfo;
}

export default function DynamicLoadingIndicator({ currentStep }: DynamicLoadingIndicatorProps) {
  const { theme } = useTheme();

  const displayText = currentStep
    ? `Schritt ${currentStep.stepNumber}/${currentStep.totalSteps}: ${currentStep.description}`
    : 'dina denkt nach...';

  return (
    <div className="dynamic-loading-indicator">
      <div style={{
        width: '60px',
        height: '60px',
        flexShrink: 0,
        zIndex: 2,
        borderRadius: '50%',
        overflow: 'hidden',
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
            objectFit: 'cover',
          }}
        >
          <source src="/dina_loading.mp4" type="video/mp4" />
        </video>
      </div>

      <div className="loading-content">
        <div
          className="loading-bubble"
          style={{
            background: theme === 'dark' ? '#1e293b' : '#ffffff',
            color: theme === 'dark' ? '#f8fafc' : '#2d3748',
            border: theme === 'dark' ? '1px solid #475569' : '1px solid #e2e8f0',
          }}
        >
          <div className="loading-inner">
            <span className="loading-text" style={{
              color: theme === 'dark' ? '#cbd5e1' : '#64748b'
            }}>
              {displayText}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
