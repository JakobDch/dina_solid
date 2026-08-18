
interface MinimalSpinnerProps {
  size?: 'small' | 'default' | 'large';
  text?: string;
}

const sizeMap = {
  small: 40,
  default: 60,
  large: 100
};

export default function MinimalSpinner({ size = 'default', text }: MinimalSpinnerProps) {
  const pixelSize = sizeMap[size];

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: text ? '16px' : 0
    }}>
      <div style={{
        width: `${pixelSize}px`,
        height: `${pixelSize}px`,
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
      {text && (
        <span style={{
          color: '#64748b',
          fontSize: '14px',
          fontWeight: 400
        }}>
          {text}
        </span>
      )}
    </div>
  );
}
