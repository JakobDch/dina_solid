import {
  Layout,
  ConfigProvider,
  theme as antdTheme
} from 'antd';
import deDE from 'antd/locale/de_DE';
import enUS from 'antd/locale/en_US';
import { useTranslation } from 'react-i18next';

import {
  BrowserRouter as Router,
  Routes,
  Route,
} from "react-router-dom";

import { useBackendHealth } from './hooks/useBackendHealth';
import AppLoadingScreen from './components/AppLoadingScreen';
import Footer from './components/layout/Footer';

import LandingPage from './pages/LandingPage';
import WorkspacesPage from './pages/WorkspacesPage';
import HeaderBar from './components/layout/HeaderBar';
import { ChatProvider } from './contexts/ChatContext';
import { ProfileProvider } from './contexts/ProfileContext';
import { ThemeProvider, useTheme } from './contexts/ThemeContext';
import { SolidAuthProvider } from './contexts/SolidAuthContext';
import { ApiKeyProvider } from './contexts/ApiKeyContext';
import ChatInterface from './components/workspace/ChatInterface';
import Profile from './components/workspace/Profile';

function ThemedApp() {
  const { theme } = useTheme();
  const { i18n } = useTranslation();

  // Ant Design ships its own strings (pagination, pickers, empty states);
  // without this they stay English inside an otherwise German interface.
  const antdLocale = i18n.resolvedLanguage === 'de' ? deDE : enUS;

  const getThemeConfig = () => {
    // New color palette
    const primaryColor = '#164475';  // Dunkelblau
    const accentColor = '#C6712F';   // Orange

    const baseConfig = {
      token: {
        fontFamily: 'Baloo Bhaijaan 2, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji"',
        colorPrimary: primaryColor,
        colorInfo: primaryColor,
        colorSuccess: '#059669',
        colorWarning: accentColor,
        colorError: '#dc2626',
        borderRadius: 8,
        boxShadow: '0 4px 16px rgba(22, 68, 117, 0.08)',
        controlHeight: 40,
        fontSize: 18,
        lineHeight: 1.6,
      },
      components: {
        Button: {
          controlHeight: 44,
          borderRadius: 12,
          fontWeight: 600,
          paddingInline: 24,
          paddingBlock: 8,
          boxShadow: '0 2px 8px rgba(22, 68, 117, 0.1)',
          primaryShadow: '0 4px 16px rgba(22, 68, 117, 0.2)',
        },
        Card: {
          borderRadiusLG: 12,
          paddingLG: 24,
        },
        Input: {
          controlHeight: 44,
          borderRadius: 12,
          paddingInline: 16,
          fontSize: 18,
        },
        Select: {
          controlHeight: 44,
          borderRadius: 12,
          fontSize: 18,
        },
        Switch: {
          colorPrimary: primaryColor,
          colorPrimaryHover: '#123a64',
        },
        Table: {
          borderRadiusLG: 8,
        },
      },
    };

    if (theme === 'dark') {
      return {
        ...baseConfig,
        algorithm: [antdTheme.darkAlgorithm],
        token: {
          ...baseConfig.token,
          colorPrimary: '#3d6a9e', // Lighter blue for dark mode
          colorInfo: '#3d6a9e',
          colorWarning: '#d4894f', // Lighter orange for dark mode

          // Background colors
          colorBgBase: '#0f172a',
          colorBgContainer: '#1e293b',
          colorBgElevated: '#334155',
          colorBgLayout: '#0f172a',
          colorBgSpotlight: '#1e293b',

          // Border colors
          colorBorder: '#475569',
          colorBorderSecondary: '#374151',

          // Text colors
          colorText: '#f8fafc',
          colorTextSecondary: '#cbd5e1',
          colorTextTertiary: '#94a3b8',
          colorTextQuaternary: '#64748b',

          // Fill colors
          colorFill: '#334155',
          colorFillSecondary: '#475569',
          colorFillTertiary: '#64748b',
          colorFillQuaternary: '#374151',

          // Component specific
          colorBgTextHover: '#334155',
          colorBgTextActive: '#475569',

          // White override for dark theme
          colorWhite: '#1e293b',
        },
        components: {
          ...baseConfig.components,
          Button: {
            ...baseConfig.components.Button,
            colorBgContainer: '#334155',
            colorBgContainerDisabled: '#1e293b',
            colorText: '#f8fafc',
            colorTextDisabled: '#64748b',
            borderColorDisabled: '#374151',
            algorithm: true, // Use algorithm for proper contrast
          },
          Card: {
            ...baseConfig.components.Card,
            colorBgContainer: '#1e293b',
            colorBorderSecondary: '#374151',
          },
          Input: {
            ...baseConfig.components.Input,
            colorBgContainer: '#334155',
            colorText: '#f8fafc',
            colorTextPlaceholder: '#94a3b8',
            colorBorder: '#475569',
          },
          Select: {
            ...baseConfig.components.Select,
            colorBgContainer: '#334155',
            colorText: '#f8fafc',
            colorBorder: '#475569',
          },
          Table: {
            ...baseConfig.components.Table,
            colorBgContainer: '#1e293b',
            headerBg: '#334155',
            colorText: '#f8fafc',
            colorTextHeading: '#f8fafc',
          },
          Layout: {
            bodyBg: '#0f172a',
            headerBg: '#1e293b',
            footerBg: '#1e293b',
            siderBg: '#1e293b',
          },
          Menu: {
            colorBgContainer: '#1e293b',
            colorText: '#f8fafc',
            colorTextSecondary: '#cbd5e1',
          }
        }
      };
    }

    return baseConfig;
  };

  const { isHealthy, isLoading, error, healthStatus, retryCount, checkHealth } = useBackendHealth({
    pollInterval: 2000,
    maxRetries: 30,
    autoStart: true
  });

  // Show loading screen while backend is starting up
  if (!isHealthy || isLoading || error) {
    return (
      <ConfigProvider theme={getThemeConfig()} locale={antdLocale}>
        <AppLoadingScreen
          isLoading={isLoading}
          error={error}
          healthStatus={healthStatus}
          retryCount={retryCount}
          maxRetries={30}
          onRetry={checkHealth}
        />
      </ConfigProvider>
    );
  }

  return (
    <ConfigProvider theme={getThemeConfig()} locale={antdLocale}>
      <Router>
        <Layout style={{
          width: "100%",
          minHeight: "100vh",
          background: theme === 'dark' ? '#0f172a' : '#ffffff'
        }}>
          <Layout.Content
            style={{
              padding: '0',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'stretch',
              background: theme === 'dark' ? '#0f172a' : '#f8fafc',
              minHeight: 'calc(100vh - 120px)',
            }}
          >
            <SolidAuthProvider>
              <ApiKeyProvider>
              <ProfileProvider>
                <ChatProvider>
                  <Routes>
                    {/* Landing page */}
                    <Route path="/" element={<LandingPage />} />
                    {/* Workspace overview */}
                    <Route path="/workspaces" element={
                      <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
                        <HeaderBar />
                        <div style={{ flex: 1 }}>
                          <WorkspacesPage />
                        </div>
                        <Footer />
                      </div>
                    } />
                    <Route path="/workspace/:id" element={
                      <WorkspacePage><ChatInterface /></WorkspacePage>
                    } />
                    <Route path="/workspace/:id/profile" element={
                      <WorkspacePage><Profile /></WorkspacePage>
                    } />
                  </Routes>
                </ChatProvider>
              </ProfileProvider>
              </ApiKeyProvider>
            </SolidAuthProvider>
          </Layout.Content>
        </Layout>
      </Router>
    </ConfigProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <ThemedApp />
    </ThemeProvider>
  );
}


/**
 * Shared shell for the workspace routes: header, page content, footer.
 *
 * The workspace itself is addressed by the :id route parameter and read by the
 * individual pages, so this wrapper only provides the surrounding chrome.
 */
function WorkspacePage({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <HeaderBar showNavigation={true} />
      <div style={{ flex: 1 }}>{children}</div>
      <Footer />
    </div>
  );
}
