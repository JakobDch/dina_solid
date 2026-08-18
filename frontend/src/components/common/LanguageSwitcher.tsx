import { Dropdown, Button } from 'antd';
import { GlobalOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import type { MenuProps } from 'antd';

const LANGUAGE_LABELS: Record<string, string> = {
  de: 'Deutsch',
  en: 'English',
};

/** Lets the user override the language detected from the browser. */
export default function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const active = i18n.resolvedLanguage ?? 'en';

  const items: MenuProps['items'] = Object.entries(LANGUAGE_LABELS).map(([code, label]) => ({
    key: code,
    label: (
      <span style={{ fontWeight: code === active ? 600 : 400 }}>
        {label}
        {code === active ? ' ✓' : ''}
      </span>
    ),
    onClick: () => {
      void i18n.changeLanguage(code);
    },
  }));

  return (
    <Dropdown menu={{ items }} placement="bottomRight" trigger={['click']}>
      <Button
        type="text"
        icon={<GlobalOutlined />}
        aria-label={t('common.language')}
        style={{ display: 'flex', alignItems: 'center', gap: 6 }}
      >
        {active.toUpperCase()}
      </Button>
    </Dropdown>
  );
}
