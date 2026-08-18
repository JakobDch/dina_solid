import { useEffect, useState } from 'react';
import { Typography, Button } from 'antd';
import { ArrowRightOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useScrollAnimation } from '../../hooks/useScrollAnimation';
import { useTypewriter } from '../../hooks/useTypewriter';

const { Title, Paragraph } = Typography;

const exampleQueries = [
  'Wie hoch ist der CO2-Fussabdruck von Produkt A?',
  'Welche Materialien verursachen die meisten Emissionen?',
  'Zeige mir die Transportwege mit dem hoechsten Energieverbrauch',
  'Vergleiche die Umweltbilanz unserer Lieferanten',
  'Welche Scope-3-Emissionen fallen in der Lieferkette an?'
];

const TypewriterDisplay = ({ isVisible }: { isVisible: boolean }) => {
  const { displayText, startTyping } = useTypewriter({
    texts: exampleQueries,
    typingSpeed: 40,
    deletingSpeed: 25,
    pauseDuration: 2500,
    loop: true
  });

  useEffect(() => {
    if (isVisible) {
      const timer = setTimeout(() => {
        startTyping();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isVisible, startTyping]);

  return (
    <div style={{
      background: 'linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%)',
      border: '2px solid #E4E8EB',
      borderRadius: '16px',
      padding: '32px 40px',
      maxWidth: '800px',
      margin: '0 auto',
      minHeight: '100px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 8px 32px rgba(22, 68, 117, 0.08)',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Subtle gradient overlay */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '4px',
        background: 'linear-gradient(90deg, #164475, #C6712F, #164475)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 3s linear infinite'
      }} />

      <div style={{
        fontSize: '1.4rem',
        color: '#164475',
        fontWeight: 500,
        lineHeight: 1.6,
        textAlign: 'center'
      }}>
        "{displayText}
        <span className="typewriter-cursor" />
        "
      </div>
    </div>
  );
};

const QueryCard = ({ query, index, isVisible }: { query: string; index: number; isVisible: boolean }) => {
  const navigate = useNavigate();

  return (
    <div
      className="example-query-card"
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0)' : 'translateY(20px)',
        transition: `all 0.5s ease-out ${index * 100}ms`
      }}
      onClick={() => navigate('/workspaces')}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '16px'
      }}>
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '8px',
          background: index % 2 === 0 ? '#e8eef5' : '#fdf3eb',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0
        }}>
          <span style={{
            fontSize: '14px',
            fontWeight: 700,
            color: index % 2 === 0 ? '#164475' : '#C6712F'
          }}>
            {index + 1}
          </span>
        </div>
        <span className="query-text">
          {query}
        </span>
        <ArrowRightOutlined style={{
          color: '#C6712F',
          opacity: 0,
          transform: 'translateX(-10px)',
          transition: 'all 0.3s ease',
          marginLeft: 'auto'
        }} className="arrow-icon" />
      </div>
      <style>{`
        .example-query-card:hover .arrow-icon {
          opacity: 1 !important;
          transform: translateX(0) !important;
        }
      `}</style>
    </div>
  );
};

export default function ExampleQueriesSection() {
  const { ref: sectionRef, isVisible: sectionVisible } = useScrollAnimation({ threshold: 0.1 });
  const [cardsVisible, setCardsVisible] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (sectionVisible) {
      const timer = setTimeout(() => {
        setCardsVisible(true);
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [sectionVisible]);

  return (
    <section
      ref={sectionRef}
      id="examples"
      style={{
        padding: '100px 48px',
        background: '#ffffff',
        position: 'relative'
      }}
    >
      {/* Section Header */}
      <div style={{
        textAlign: 'center',
        marginBottom: '48px',
        opacity: sectionVisible ? 1 : 0,
        transform: sectionVisible ? 'translateY(0)' : 'translateY(30px)',
        transition: 'all 0.6s ease-out'
      }}>
        <Title
          level={2}
          style={{
            color: '#164475',
            marginBottom: '16px',
            fontWeight: 700,
            fontSize: '2.5rem'
          }}
        >
          Das kannst du fragen
        </Title>
        <Paragraph style={{
          color: '#64748b',
          fontSize: '1.2rem',
          maxWidth: '600px',
          margin: '0 auto',
          lineHeight: 1.6
        }}>
          Stelle komplexe Nachhaltigkeitsfragen in einfacher Sprache
        </Paragraph>
      </div>

      {/* Typewriter Display */}
      <div style={{
        marginBottom: '64px',
        opacity: sectionVisible ? 1 : 0,
        transform: sectionVisible ? 'translateY(0)' : 'translateY(20px)',
        transition: 'all 0.6s ease-out 0.2s'
      }}>
        <TypewriterDisplay isVisible={sectionVisible} />
      </div>

      {/* Query Cards Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))',
        gap: '16px',
        maxWidth: '900px',
        margin: '0 auto 48px'
      }}>
        {exampleQueries.map((query, index) => (
          <QueryCard
            key={query}
            query={query}
            index={index}
            isVisible={cardsVisible}
          />
        ))}
      </div>

      {/* CTA Button */}
      <div style={{
        textAlign: 'center',
        opacity: cardsVisible ? 1 : 0,
        transform: cardsVisible ? 'translateY(0)' : 'translateY(20px)',
        transition: 'all 0.5s ease-out 0.6s'
      }}>
        <Button
          type="primary"
          size="large"
          onClick={() => navigate('/workspaces')}
          style={{
            background: 'linear-gradient(135deg, #C6712F 0%, #a85d26 100%)',
            border: 'none',
            borderRadius: '12px',
            fontWeight: 600,
            padding: '0 48px',
            height: '56px',
            fontSize: '1.15rem',
            boxShadow: '0 8px 24px rgba(198, 113, 47, 0.3)',
            transition: 'all 0.3s ease'
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-3px)';
            e.currentTarget.style.boxShadow = '0 12px 32px rgba(198, 113, 47, 0.4)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = '0 8px 24px rgba(198, 113, 47, 0.3)';
          }}
        >
          Jetzt eigene Fragen stellen
          <ArrowRightOutlined style={{ marginLeft: '8px' }} />
        </Button>
      </div>
    </section>
  );
}
