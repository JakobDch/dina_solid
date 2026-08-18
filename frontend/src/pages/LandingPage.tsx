import { Button, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  LockOutlined,
  CheckCircleOutlined,
  CloudServerOutlined
} from '@ant-design/icons';
import LandingPageImage from '../assets/dina_landing_page_image.png';
import Footer from '../components/layout/Footer';
import HeaderBar from '../components/layout/HeaderBar';
import ProcessFlowSection from '../components/landing/ProcessFlowSection';
import BenefitsSection from '../components/landing/BenefitsSection';
import ExampleQueriesSection from '../components/landing/ExampleQueriesSection';
import { useTranslation } from 'react-i18next';

const { Title, Text, Paragraph } = Typography;

export default function LandingPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      background: '#ffffff'
    }}>
      {/* Header */}
      <HeaderBar showNavigation={true} />

      {/* Hero Section */}
      <section style={{
        padding: '80px 48px',
        background: '#f8f9fa',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '48px',
        flexWrap: 'wrap'
      }}>
        <div style={{ flex: '1', minWidth: '300px', maxWidth: '600px' }}>
          <Title
            level={1}
            style={{
              fontSize: '3rem',
              fontWeight: 800,
              color: '#164475',
              marginBottom: '24px',
              lineHeight: 1.2
            }}
          >
            {t('landing.headline')}
          </Title>
          <Paragraph style={{
            fontSize: '1.25rem',
            color: '#475569',
            lineHeight: 1.6,
            marginBottom: '32px'
          }}>
            {t('landing.subline')}
          </Paragraph>
          <Button
            type="primary"
            size="large"
            onClick={() => navigate('/workspaces')}
            style={{
              background: '#C6712F',
              border: 'none',
              borderRadius: '8px',
              fontWeight: 600,
              padding: '0 32px',
              height: '52px',
              fontSize: '1.1rem'
            }}
          >
            {t('landing.getStarted')}
          </Button>
        </div>

        {/* Chat Demo Image */}
        <div style={{
          flex: '1',
          minWidth: '300px',
          maxWidth: '550px',
          display: 'flex',
          justifyContent: 'center'
        }}>
          <img
            src={LandingPageImage}
            alt="dina Chat Demo"
            style={{
              width: '100%',
              height: 'auto',
              borderRadius: '12px',
              boxShadow: '0 10px 40px rgba(22, 68, 117, 0.15)'
            }}
          />
        </div>
      </section>

      {/* Process Flow Section - How it works */}
      <ProcessFlowSection />

      {/* Benefits Section - Feature Cards */}
      <BenefitsSection />

      {/* Example Queries Section - Typewriter */}
      <ExampleQueriesSection />

      {/* Security Section */}
      <section id="security" style={{
        padding: '80px 48px',
        background: '#f8f9fa'
      }}>
        <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
          <Title
            level={2}
            style={{
              textAlign: 'center',
              color: '#164475',
              marginBottom: '16px',
              fontWeight: 700
            }}
          >
            {t('landing.securityHeading')}
          </Title>
          <Paragraph style={{
            textAlign: 'center',
            color: '#64748b',
            fontSize: '1.1rem',
            maxWidth: '600px',
            margin: '0 auto 48px'
          }}>
            {t('landing.securitySub')}
          </Paragraph>

          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: '24px'
          }}>
            <div style={{
              background: '#ffffff',
              borderRadius: '12px',
              padding: '24px',
              border: '1px solid #E4E8EB',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '16px'
            }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: '#164475',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <LockOutlined style={{ fontSize: '22px', color: '#ffffff' }} />
              </div>
              <div>
                <Text style={{ color: '#164475', fontWeight: 600, fontSize: '1rem', display: 'block', marginBottom: '4px' }}>
                  {t('landing.encryptionTitle')}
                </Text>
                <Text style={{ color: '#64748b', fontSize: '0.95rem' }}>
                  {t('landing.encryptionText')}
                </Text>
              </div>
            </div>

            <div style={{
              background: '#ffffff',
              borderRadius: '12px',
              padding: '24px',
              border: '1px solid #E4E8EB',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '16px'
            }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: '#164475',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <CheckCircleOutlined style={{ fontSize: '22px', color: '#ffffff' }} />
              </div>
              <div>
                <Text style={{ color: '#164475', fontWeight: 600, fontSize: '1rem', display: 'block', marginBottom: '4px' }}>
                  {t('landing.gdprTitle')}
                </Text>
                <Text style={{ color: '#64748b', fontSize: '0.95rem' }}>
                  {t('landing.gdprText')}
                </Text>
              </div>
            </div>

            <div style={{
              background: '#ffffff',
              borderRadius: '12px',
              padding: '24px',
              border: '1px solid #E4E8EB',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '16px'
            }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: '#164475',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0
              }}>
                <CloudServerOutlined style={{ fontSize: '22px', color: '#ffffff' }} />
              </div>
              <div>
                <Text style={{ color: '#164475', fontWeight: 600, fontSize: '1rem', display: 'block', marginBottom: '4px' }}>
                  {t('landing.onPremTitle')}
                </Text>
                <Text style={{ color: '#64748b', fontSize: '0.95rem' }}>
                  {t('landing.onPremText')}
                </Text>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <Footer />
    </div>
  );
}
