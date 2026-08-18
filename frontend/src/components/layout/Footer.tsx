import { useTranslation } from 'react-i18next';
import DinaLogoWhite from '../../assets/dina_logo_2026_white.png';

export default function Footer() {
  const { t } = useTranslation();

  return (
    <footer style={{
      background: '#164475',
      padding: '40px 48px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
      flexWrap: 'wrap',
      gap: '24px',
      position: 'relative',
      overflow: 'hidden'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <img
          src={DinaLogoWhite}
          alt="dina Logo"
          style={{
            height: '40px',
            width: 'auto'
          }}
        />
      </div>
      <nav style={{ display: 'flex', gap: '32px' }}>
        <a href="#" style={{ color: 'rgba(255,255,255,0.8)', textDecoration: 'none' }}>
          {t('footer.imprint')}
        </a>
        <a href="#" style={{ color: 'rgba(255,255,255,0.8)', textDecoration: 'none' }}>
          {t('footer.privacy')}
        </a>
        <a href="#" style={{ color: 'rgba(255,255,255,0.8)', textDecoration: 'none' }}>
          {t('footer.contact')}
        </a>
      </nav>
    </footer>
  );
}
