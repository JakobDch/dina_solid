// Utility functions extracted from App.tsx

import i18n from '../i18n';

/** Map the active i18n language onto a BCP-47 locale for Intl formatting. */
const activeLocale = () => (i18n.language?.startsWith('de') ? 'de-DE' : 'en-GB');

export const formatDateTime = (iso: string) => {
  try {
    if (!iso) {
      console.error('formatDateTime received undefined or null ISO string');
      return i18n.t('errors.invalidDate');
    }
    const options: Intl.DateTimeFormatOptions = {
      timeZone: 'Europe/Berlin',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    };
    let isoToParse = iso;
    if (!iso.includes('Z') && !iso.match(/[+-]\d{2}:\d{2}$/)) {
      isoToParse += 'Z';
    }
    const date = new Date(isoToParse);
    if (isNaN(date.getTime())) {
      console.error('Invalid date after parsing:', iso);
      return i18n.t('errors.invalidDate');
    }
    const formatter = new Intl.DateTimeFormat(activeLocale(), options);
    return formatter.format(date).replace(',', '');
  } catch (e: any) {
    console.error('formatDateTime failed:', e.message);
    console.error('Input ISO was:', iso);
    return iso || i18n.t('errors.dateError');
  }
};

export const formatFileSize = (bytes: number) => {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)).toLocaleString(activeLocale()) + ' ' + sizes[i];
};
