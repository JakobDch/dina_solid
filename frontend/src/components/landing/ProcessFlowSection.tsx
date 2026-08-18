import { useRef, useEffect, useState } from 'react';
import { Typography } from 'antd';
import {
  FolderOpenOutlined,
  CloudUploadOutlined,
  MessageOutlined,
  LineChartOutlined
} from '@ant-design/icons';
import { useScrollAnimation } from '../../hooks/useScrollAnimation';

const { Title, Text, Paragraph } = Typography;

interface ProcessStep {
  number: number;
  icon: React.ReactNode;
  title: string;
  description: string;
  detail: string;
  iconAnimation: string;
  direction: 'left' | 'right';
}

const steps: ProcessStep[] = [
  {
    number: 1,
    icon: <FolderOpenOutlined style={{ fontSize: '32px', color: '#164475' }} />,
    title: 'Projekt anlegen',
    description: 'Erstelle einen Workspace fuer dein Nachhaltigkeitsprojekt',
    detail: 'Organisiere deine Analysen in uebersichtlichen Projekten',
    iconAnimation: 'icon-pulse',
    direction: 'left'
  },
  {
    number: 2,
    icon: <CloudUploadOutlined style={{ fontSize: '32px', color: '#C6712F' }} />,
    title: 'Daten verbinden',
    description: 'Verbinde deine Unternehmensdaten',
    detail: 'Lade Produktdaten, Lieferketten-Informationen und Umweltkennzahlen hoch',
    iconAnimation: 'icon-bounce',
    direction: 'right'
  },
  {
    number: 3,
    icon: <MessageOutlined style={{ fontSize: '32px', color: '#164475' }} />,
    title: 'Fragen stellen',
    description: 'Stelle Fragen in natuerlicher Sprache',
    detail: 'Keine Programmier- oder Datenbankkenntnisse erforderlich',
    iconAnimation: 'icon-float',
    direction: 'left'
  },
  {
    number: 4,
    icon: <LineChartOutlined style={{ fontSize: '32px', color: '#C6712F' }} />,
    title: 'Insights erhalten',
    description: 'Erhalte fundierte Nachhaltigkeits-Insights',
    detail: 'Praezise Antworten mit vollstaendiger Nachvollziehbarkeit',
    iconAnimation: 'icon-pulse',
    direction: 'right'
  }
];

const ConnectorLine = ({ isVisible, index }: { isVisible: boolean; index: number }) => {
  return (
    <div style={{
      position: 'relative',
      height: '60px',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center'
    }}>
      <svg
        width="4"
        height="60"
        className={`connector-line ${isVisible ? 'visible' : ''}`}
        style={{
          overflow: 'visible'
        }}
      >
        <defs>
          <linearGradient id={`lineGradient-${index}`} x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#164475" />
            <stop offset="100%" stopColor="#C6712F" />
          </linearGradient>
        </defs>
        <path
          d="M2,0 L2,60"
          stroke={`url(#lineGradient-${index})`}
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          style={{
            strokeDasharray: 60,
            strokeDashoffset: isVisible ? 0 : 60,
            transition: 'stroke-dashoffset 0.8s ease-out',
            transitionDelay: `${index * 200}ms`
          }}
        />
      </svg>
    </div>
  );
};

const StepCard = ({ step, isVisible, delay }: { step: ProcessStep; isVisible: boolean; delay: number }) => {
  const isLeft = step.direction === 'left';

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isLeft ? 'flex-start' : 'flex-end',
        width: '100%',
        maxWidth: '900px',
        margin: '0 auto',
        paddingLeft: isLeft ? '0' : '20%',
        paddingRight: isLeft ? '20%' : '0',
        opacity: isVisible ? 1 : 0,
        transform: isVisible
          ? 'translateX(0)'
          : `translateX(${isLeft ? '-50px' : '50px'})`,
        transition: `all 0.6s ease-out ${delay}ms`
      }}
    >
      <div
        style={{
          background: 'linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%)',
          border: '1px solid #E4E8EB',
          borderRadius: '20px',
          padding: '28px 32px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '20px',
          boxShadow: '0 4px 20px rgba(22, 68, 117, 0.08)',
          transition: 'all 0.3s ease',
          cursor: 'default',
          maxWidth: '500px',
          width: '100%'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'translateY(-4px)';
          e.currentTarget.style.boxShadow = '0 12px 32px rgba(22, 68, 117, 0.12)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = '0 4px 20px rgba(22, 68, 117, 0.08)';
        }}
      >
        {/* Step Number Badge */}
        <div style={{
          position: 'relative',
          flexShrink: 0
        }}>
          <div style={{
            width: '56px',
            height: '56px',
            borderRadius: '16px',
            background: step.number % 2 === 1
              ? 'linear-gradient(135deg, #e8eef5 0%, #d1dde8 100%)'
              : 'linear-gradient(135deg, #fdf3eb 0%, #f9e2cc 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            position: 'relative'
          }}>
            <div className={isVisible ? step.iconAnimation : ''}>
              {step.icon}
            </div>
          </div>
          <div style={{
            position: 'absolute',
            top: '-8px',
            right: '-8px',
            width: '24px',
            height: '24px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #164475 0%, #1a5a9e 100%)',
            color: 'white',
            fontSize: '12px',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 8px rgba(22, 68, 117, 0.3)'
          }}>
            {step.number}
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1 }}>
          <Title level={4} style={{
            color: '#164475',
            marginBottom: '8px',
            fontSize: '1.25rem',
            fontWeight: 700
          }}>
            {step.title}
          </Title>
          <Text style={{
            color: '#475569',
            fontSize: '1rem',
            display: 'block',
            marginBottom: '4px',
            fontWeight: 500
          }}>
            {step.description}
          </Text>
          <Text style={{
            color: '#64748b',
            fontSize: '0.9rem'
          }}>
            {step.detail}
          </Text>
        </div>
      </div>
    </div>
  );
};

export default function ProcessFlowSection() {
  const { ref: sectionRef, isVisible: sectionVisible } = useScrollAnimation({ threshold: 0.1 });
  const [visibleSteps, setVisibleSteps] = useState<boolean[]>(new Array(steps.length).fill(false));
  const stepRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const observers: IntersectionObserver[] = [];

    stepRefs.current.forEach((ref, index) => {
      if (ref) {
        const observer = new IntersectionObserver(
          ([entry]) => {
            if (entry.isIntersecting) {
              setVisibleSteps(prev => {
                const newState = [...prev];
                newState[index] = true;
                return newState;
              });
              observer.unobserve(entry.target);
            }
          },
          { threshold: 0.3, rootMargin: '0px 0px -50px 0px' }
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
      id="how-it-works"
      style={{
        padding: '100px 48px',
        background: '#ffffff',
        position: 'relative',
        overflow: 'hidden'
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
          So funktioniert DINa
        </Title>
        <Paragraph style={{
          color: '#64748b',
          fontSize: '1.2rem',
          maxWidth: '600px',
          margin: '0 auto',
          lineHeight: 1.6
        }}>
          In vier einfachen Schritten von der Datenanbindung zu wertvollen Nachhaltigkeits-Insights
        </Paragraph>
      </div>

      {/* Process Flow */}
      <div style={{
        maxWidth: '1000px',
        margin: '0 auto',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center'
      }}>
        {steps.map((step, index) => (
          <div
            key={step.number}
            ref={(el) => { stepRefs.current[index] = el; }}
            style={{ width: '100%' }}
          >
            <StepCard
              step={step}
              isVisible={visibleSteps[index]}
              delay={index * 100}
            />
            {index < steps.length - 1 && (
              <ConnectorLine
                isVisible={visibleSteps[index]}
                index={index}
              />
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
