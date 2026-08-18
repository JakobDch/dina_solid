import { useRef, useEffect, useState } from 'react';
import { Typography } from 'antd';
import {
  GlobalOutlined,
  ApartmentOutlined,
  BarChartOutlined,
  CompassOutlined,
  ThunderboltOutlined,
  CommentOutlined,
  DownloadOutlined,
  SafetyCertificateOutlined
} from '@ant-design/icons';
import { useScrollAnimation } from '../../hooks/useScrollAnimation';
import { useCounter } from '../../hooks/useCounter';

const { Title, Text, Paragraph } = Typography;

interface BenefitCard {
  icon: React.ReactNode;
  title: string;
  description: string;
  iconBgColor: string;
  animationType: 'counter' | 'sparkle' | 'nodes' | 'bars' | 'search' | 'chat' | 'files' | 'check';
  counterValue?: number;
  counterSuffix?: string;
}

const benefits: BenefitCard[] = [
  {
    icon: <GlobalOutlined style={{ fontSize: '28px', color: '#164475' }} />,
    title: 'CO2-Bilanzierung',
    description: 'Berechne CO2-Fussabdruecke fuer Produkte und Prozesse automatisch',
    iconBgColor: '#e8eef5',
    animationType: 'counter',
    counterValue: 90,
    counterSuffix: '% schneller'
  },
  {
    icon: <ApartmentOutlined style={{ fontSize: '28px', color: '#C6712F' }} />,
    title: 'Lieferketten-Analyse',
    description: 'Analysiere Umweltauswirkungen entlang der gesamten Wertschoepfungskette',
    iconBgColor: '#fdf3eb',
    animationType: 'nodes'
  },
  {
    icon: <BarChartOutlined style={{ fontSize: '28px', color: '#164475' }} />,
    title: 'Daten visualisieren',
    description: 'Visualisiere deine Datenstrukturen als interaktive Graphen und Diagramme',
    iconBgColor: '#e8eef5',
    animationType: 'bars'
  },
  {
    icon: <CompassOutlined style={{ fontSize: '28px', color: '#C6712F' }} />,
    title: 'Daten erkunden',
    description: 'Stelle einfache Verstaendnisfragen, um deine Daten zu erkunden und kennenzulernen',
    iconBgColor: '#fdf3eb',
    animationType: 'search'
  },
  {
    icon: <ThunderboltOutlined style={{ fontSize: '28px', color: '#164475' }} />,
    title: 'Intelligente Auswertung',
    description: 'KI versteht komplexe Zusammenhaenge und liefert praezise Antworten',
    iconBgColor: '#e8eef5',
    animationType: 'sparkle'
  },
  {
    icon: <CommentOutlined style={{ fontSize: '28px', color: '#C6712F' }} />,
    title: 'Interaktive Klaerung',
    description: 'Bei Unklarheiten fragt DINa gezielt nach - wie ein Experte',
    iconBgColor: '#fdf3eb',
    animationType: 'chat'
  },
  {
    icon: <DownloadOutlined style={{ fontSize: '28px', color: '#164475' }} />,
    title: 'Flexible Exporte',
    description: 'Exportiere Ergebnisse in verschiedenen Formaten fuer deine Reports',
    iconBgColor: '#e8eef5',
    animationType: 'files'
  },
  {
    icon: <SafetyCertificateOutlined style={{ fontSize: '28px', color: '#C6712F' }} />,
    title: 'Volle Transparenz',
    description: 'Nachvollziehbare Ergebnisse mit vollstaendiger Quellenangabe',
    iconBgColor: '#fdf3eb',
    animationType: 'check'
  }
];

// Mini animated components for each card type
const CounterAnimation = ({ value, suffix, isVisible }: { value: number; suffix: string; isVisible: boolean }) => {
  const { count, startCounting } = useCounter({
    end: value,
    duration: 2000,
    easing: 'easeOut'
  });

  useEffect(() => {
    if (isVisible) {
      startCounting();
    }
  }, [isVisible, startCounting]);

  return (
    <div style={{
      marginTop: '12px',
      fontSize: '1.5rem',
      fontWeight: 700,
      color: '#C6712F',
      opacity: isVisible ? 1 : 0,
      transition: 'opacity 0.3s ease'
    }}
    className={isVisible ? 'animated-counter' : ''}
    >
      bis zu {count}{suffix}
    </div>
  );
};

const NodesAnimation = ({ isVisible }: { isVisible: boolean }) => (
  <div style={{
    display: 'flex',
    gap: '4px',
    marginTop: '12px',
    alignItems: 'center',
    justifyContent: 'center'
  }}>
    {[0, 1, 2].map((i) => (
      <div key={i} style={{
        display: 'flex',
        alignItems: 'center'
      }}>
        <div style={{
          width: '12px',
          height: '12px',
          borderRadius: '50%',
          background: i % 2 === 0 ? '#164475' : '#C6712F',
          opacity: isVisible ? 1 : 0,
          transform: isVisible ? 'scale(1)' : 'scale(0)',
          transition: `all 0.4s ease ${i * 200}ms`
        }} />
        {i < 2 && (
          <div style={{
            width: '20px',
            height: '2px',
            background: 'linear-gradient(90deg, #164475, #C6712F)',
            opacity: isVisible ? 1 : 0,
            transform: isVisible ? 'scaleX(1)' : 'scaleX(0)',
            transformOrigin: 'left',
            transition: `all 0.4s ease ${i * 200 + 100}ms`
          }} />
        )}
      </div>
    ))}
  </div>
);

const BarsAnimation = ({ isVisible }: { isVisible: boolean }) => (
  <div style={{
    display: 'flex',
    gap: '4px',
    marginTop: '12px',
    alignItems: 'flex-end',
    justifyContent: 'center',
    height: '30px'
  }}>
    {[60, 100, 40, 80, 50].map((height, i) => (
      <div key={i} style={{
        width: '8px',
        height: isVisible ? `${height}%` : '0%',
        background: i % 2 === 0 ? '#164475' : '#C6712F',
        borderRadius: '2px',
        transition: `height 0.5s ease ${i * 100}ms`
      }} />
    ))}
  </div>
);

const SparkleAnimation = ({ isVisible }: { isVisible: boolean }) => (
  <div className="sparkle-container" style={{
    position: 'relative',
    width: '40px',
    height: '20px',
    margin: '12px auto 0'
  }}>
    {isVisible && (
      <>
        <div className="sparkle" style={{ top: '0', left: '0' }} />
        <div className="sparkle" style={{ top: '10px', left: '15px', animationDelay: '0.3s' }} />
        <div className="sparkle" style={{ top: '0', left: '30px', animationDelay: '0.6s' }} />
      </>
    )}
  </div>
);

const SearchAnimation = ({ isVisible }: { isVisible: boolean }) => (
  <div style={{
    marginTop: '12px',
    display: 'flex',
    justifyContent: 'center',
    gap: '8px'
  }}>
    <div style={{
      width: '20px',
      height: '20px',
      borderRadius: '50%',
      border: '3px solid #164475',
      opacity: isVisible ? 1 : 0,
      transform: isVisible ? 'rotate(0deg)' : 'rotate(-90deg)',
      transition: 'all 0.5s ease'
    }} />
    <div style={{
      fontSize: '16px',
      color: '#C6712F',
      opacity: isVisible ? 1 : 0,
      transform: isVisible ? 'translateX(0)' : 'translateX(-10px)',
      transition: 'all 0.5s ease 0.2s'
    }}>
      ?
    </div>
  </div>
);

const ChatAnimation = ({ isVisible }: { isVisible: boolean }) => (
  <div style={{
    marginTop: '12px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    alignItems: 'center'
  }}>
    {[0, 1].map((i) => (
      <div key={i} style={{
        width: i === 0 ? '40px' : '30px',
        height: '8px',
        borderRadius: '4px',
        background: i === 0 ? '#164475' : '#C6712F',
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateX(0)' : `translateX(${i === 0 ? '-20px' : '20px'})`,
        transition: `all 0.4s ease ${i * 200}ms`
      }} />
    ))}
  </div>
);

const FilesAnimation = ({ isVisible }: { isVisible: boolean }) => (
  <div style={{
    marginTop: '12px',
    display: 'flex',
    justifyContent: 'center',
    gap: '4px'
  }}>
    {['JSON', 'CSV', 'XML'].map((format, i) => (
      <div key={format} style={{
        padding: '2px 6px',
        fontSize: '10px',
        fontWeight: 600,
        borderRadius: '4px',
        background: i % 2 === 0 ? '#e8eef5' : '#fdf3eb',
        color: i % 2 === 0 ? '#164475' : '#C6712F',
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0) rotate(0deg)' : 'translateY(10px) rotate(-10deg)',
        transition: `all 0.4s ease ${i * 100}ms`
      }}>
        {format}
      </div>
    ))}
  </div>
);

const CheckAnimation = ({ isVisible }: { isVisible: boolean }) => (
  <div style={{
    marginTop: '12px',
    display: 'flex',
    justifyContent: 'center',
    gap: '8px'
  }}>
    {[0, 1, 2].map((i) => (
      <svg key={i} width="16" height="16" viewBox="0 0 16 16" style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'scale(1)' : 'scale(0)',
        transition: `all 0.3s ease ${i * 150}ms`
      }}>
        <circle cx="8" cy="8" r="7" fill={i % 2 === 0 ? '#164475' : '#C6712F'} />
        <path
          d="M4 8 L7 11 L12 5"
          stroke="white"
          strokeWidth="2"
          fill="none"
          strokeLinecap="round"
          strokeLinejoin="round"
          style={{
            strokeDasharray: 24,
            strokeDashoffset: isVisible ? 0 : 24,
            transition: `stroke-dashoffset 0.4s ease ${i * 150 + 200}ms`
          }}
        />
      </svg>
    ))}
  </div>
);

const AnimationComponent = ({ type, isVisible, counterValue, counterSuffix }: {
  type: BenefitCard['animationType'];
  isVisible: boolean;
  counterValue?: number;
  counterSuffix?: string;
}) => {
  switch (type) {
    case 'counter':
      return <CounterAnimation value={counterValue || 0} suffix={counterSuffix || ''} isVisible={isVisible} />;
    case 'nodes':
      return <NodesAnimation isVisible={isVisible} />;
    case 'bars':
      return <BarsAnimation isVisible={isVisible} />;
    case 'sparkle':
      return <SparkleAnimation isVisible={isVisible} />;
    case 'search':
      return <SearchAnimation isVisible={isVisible} />;
    case 'chat':
      return <ChatAnimation isVisible={isVisible} />;
    case 'files':
      return <FilesAnimation isVisible={isVisible} />;
    case 'check':
      return <CheckAnimation isVisible={isVisible} />;
    default:
      return null;
  }
};

const BenefitCardComponent = ({ benefit, isVisible, delay }: {
  benefit: BenefitCard;
  isVisible: boolean;
  delay: number;
}) => (
  <div
    className="landing-feature-card"
    style={{
      background: 'linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%)',
      border: '1px solid #E4E8EB',
      borderRadius: '20px',
      padding: '28px',
      textAlign: 'center',
      opacity: isVisible ? 1 : 0,
      transform: isVisible ? 'translateY(0)' : 'translateY(30px)',
      transition: `all 0.5s ease-out ${delay}ms`,
      cursor: 'default',
      minHeight: '220px',
      display: 'flex',
      flexDirection: 'column'
    }}
    onMouseEnter={(e) => {
      e.currentTarget.style.transform = 'translateY(-8px)';
      e.currentTarget.style.boxShadow = '0 20px 40px rgba(22, 68, 117, 0.12)';
      e.currentTarget.style.borderColor = '#164475';
    }}
    onMouseLeave={(e) => {
      e.currentTarget.style.transform = isVisible ? 'translateY(0)' : 'translateY(30px)';
      e.currentTarget.style.boxShadow = 'none';
      e.currentTarget.style.borderColor = '#E4E8EB';
    }}
  >
    {/* Icon */}
    <div style={{
      width: '64px',
      height: '64px',
      background: benefit.iconBgColor,
      borderRadius: '16px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      margin: '0 auto 16px'
    }}>
      <div className={isVisible ? 'icon-float' : ''}>
        {benefit.icon}
      </div>
    </div>

    {/* Title */}
    <Title level={4} style={{
      color: '#164475',
      marginBottom: '8px',
      fontSize: '1.15rem',
      fontWeight: 700
    }}>
      {benefit.title}
    </Title>

    {/* Description */}
    <Text style={{
      color: '#64748b',
      fontSize: '0.95rem',
      lineHeight: 1.5,
      flex: 1
    }}>
      {benefit.description}
    </Text>

    {/* Animated element */}
    <AnimationComponent
      type={benefit.animationType}
      isVisible={isVisible}
      counterValue={benefit.counterValue}
      counterSuffix={benefit.counterSuffix}
    />
  </div>
);

export default function BenefitsSection() {
  const { ref: sectionRef, isVisible: sectionVisible } = useScrollAnimation({ threshold: 0.05 });
  const [visibleCards, setVisibleCards] = useState<boolean[]>(new Array(benefits.length).fill(false));
  const cardRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const observers: IntersectionObserver[] = [];

    cardRefs.current.forEach((ref, index) => {
      if (ref) {
        const observer = new IntersectionObserver(
          ([entry]) => {
            if (entry.isIntersecting) {
              setVisibleCards(prev => {
                const newState = [...prev];
                newState[index] = true;
                return newState;
              });
              observer.unobserve(entry.target);
            }
          },
          { threshold: 0.2, rootMargin: '0px 0px -30px 0px' }
        );
        observer.observe(ref);
        observers.push(observer);
      }
    });

    return () => {
      observers.forEach(observer => observer.disconnect());
    };
  }, []);

  return (
    <section
      ref={sectionRef}
      id="benefits"
      style={{
        padding: '100px 48px',
        background: '#f8f9fa',
        position: 'relative'
      }}
    >
      {/* Section Header */}
      <div style={{
        textAlign: 'center',
        marginBottom: '64px',
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
          Deine Vorteile
        </Title>
        <Paragraph style={{
          color: '#64748b',
          fontSize: '1.2rem',
          maxWidth: '600px',
          margin: '0 auto',
          lineHeight: 1.6
        }}>
          Entdecke, wie DINa deine Nachhaltigkeitsanalysen revolutioniert
        </Paragraph>
      </div>

      {/* Benefits Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
        gap: '24px',
        maxWidth: '1200px',
        margin: '0 auto'
      }}>
        {benefits.map((benefit, index) => (
          <div
            key={benefit.title}
            ref={(el) => { cardRefs.current[index] = el; }}
          >
            <BenefitCardComponent
              benefit={benefit}
              isVisible={visibleCards[index]}
              delay={index * 80}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
