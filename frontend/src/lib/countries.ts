// Countries with ISO 3166-1 alpha-2 codes, flags, dial codes, and EU VAT prefixes

export interface Country {
  code: string // ISO 3166-1 alpha-2 (e.g., "US")
  name: string // Display name
  flag: string // Emoji flag
  dialCode: string // E.164 dial code (e.g., "+1")
  vatPrefix?: string // Only for EU countries with VAT
}

// EU countries with their VAT ID prefixes
const EU_VAT_PREFIXES: Record<string, string> = {
  AT: 'ATU', // Austria
  BE: 'BE', // Belgium
  BG: 'BG', // Bulgaria
  HR: 'HR', // Croatia
  CY: 'CY', // Cyprus
  CZ: 'CZ', // Czech Republic
  DK: 'DK', // Denmark
  EE: 'EE', // Estonia
  FI: 'FI', // Finland
  FR: 'FR', // France
  DE: 'DE', // Germany
  GR: 'EL', // Greece (uses EL prefix)
  HU: 'HU', // Hungary
  IE: 'IE', // Ireland
  IT: 'IT', // Italy
  LV: 'LV', // Latvia
  LT: 'LT', // Lithuania
  LU: 'LU', // Luxembourg
  MT: 'MT', // Malta
  NL: 'NL', // Netherlands
  PL: 'PL', // Poland
  PT: 'PT', // Portugal
  RO: 'RO', // Romania
  SK: 'SK', // Slovakia
  SI: 'SI', // Slovenia
  ES: 'ES', // Spain
  SE: 'SE', // Sweden
}

// E.164 dial codes by country code
const DIAL_CODES: Record<string, string> = {
  AF: '+93',
  AL: '+355',
  DZ: '+213',
  AD: '+376',
  AO: '+244',
  AR: '+54',
  AM: '+374',
  AU: '+61',
  AT: '+43',
  AZ: '+994',
  BS: '+1',
  BH: '+973',
  BD: '+880',
  BY: '+375',
  BE: '+32',
  BZ: '+501',
  BJ: '+229',
  BT: '+975',
  BO: '+591',
  BA: '+387',
  BW: '+267',
  BR: '+55',
  BN: '+673',
  BG: '+359',
  BF: '+226',
  BI: '+257',
  KH: '+855',
  CM: '+237',
  CA: '+1',
  CV: '+238',
  CF: '+236',
  TD: '+235',
  CL: '+56',
  CN: '+86',
  CO: '+57',
  KM: '+269',
  CG: '+242',
  CR: '+506',
  HR: '+385',
  CU: '+53',
  CY: '+357',
  CZ: '+420',
  DK: '+45',
  DJ: '+253',
  DM: '+1',
  DO: '+1',
  EC: '+593',
  EG: '+20',
  SV: '+503',
  GQ: '+240',
  ER: '+291',
  EE: '+372',
  ET: '+251',
  FJ: '+679',
  FI: '+358',
  FR: '+33',
  GA: '+241',
  GM: '+220',
  GE: '+995',
  DE: '+49',
  GH: '+233',
  GR: '+30',
  GD: '+1',
  GT: '+502',
  GN: '+224',
  GW: '+245',
  GY: '+592',
  HT: '+509',
  HN: '+504',
  HK: '+852',
  HU: '+36',
  IS: '+354',
  IN: '+91',
  ID: '+62',
  IR: '+98',
  IQ: '+964',
  IE: '+353',
  IL: '+972',
  IT: '+39',
  JM: '+1',
  JP: '+81',
  JO: '+962',
  KZ: '+7',
  KE: '+254',
  KI: '+686',
  KP: '+850',
  KR: '+82',
  KW: '+965',
  KG: '+996',
  LA: '+856',
  LV: '+371',
  LB: '+961',
  LS: '+266',
  LR: '+231',
  LY: '+218',
  LI: '+423',
  LT: '+370',
  LU: '+352',
  MO: '+853',
  MK: '+389',
  MG: '+261',
  MW: '+265',
  MY: '+60',
  MV: '+960',
  ML: '+223',
  MT: '+356',
  MH: '+692',
  MR: '+222',
  MU: '+230',
  MX: '+52',
  FM: '+691',
  MD: '+373',
  MC: '+377',
  MN: '+976',
  ME: '+382',
  MA: '+212',
  MZ: '+258',
  MM: '+95',
  NA: '+264',
  NR: '+674',
  NP: '+977',
  NL: '+31',
  NZ: '+64',
  NI: '+505',
  NE: '+227',
  NG: '+234',
  NO: '+47',
  OM: '+968',
  PK: '+92',
  PW: '+680',
  PS: '+970',
  PA: '+507',
  PG: '+675',
  PY: '+595',
  PE: '+51',
  PH: '+63',
  PL: '+48',
  PT: '+351',
  QA: '+974',
  RO: '+40',
  RU: '+7',
  RW: '+250',
  KN: '+1',
  LC: '+1',
  VC: '+1',
  WS: '+685',
  SM: '+378',
  ST: '+239',
  SA: '+966',
  SN: '+221',
  RS: '+381',
  SC: '+248',
  SL: '+232',
  SG: '+65',
  SK: '+421',
  SI: '+386',
  SB: '+677',
  SO: '+252',
  ZA: '+27',
  SS: '+211',
  ES: '+34',
  LK: '+94',
  SD: '+249',
  SR: '+597',
  SZ: '+268',
  SE: '+46',
  CH: '+41',
  SY: '+963',
  TW: '+886',
  TJ: '+992',
  TZ: '+255',
  TH: '+66',
  TL: '+670',
  TG: '+228',
  TO: '+676',
  TT: '+1',
  TN: '+216',
  TR: '+90',
  TM: '+993',
  TV: '+688',
  UG: '+256',
  UA: '+380',
  AE: '+971',
  GB: '+44',
  US: '+1',
  UY: '+598',
  UZ: '+998',
  VU: '+678',
  VA: '+39',
  VE: '+58',
  VN: '+84',
  YE: '+967',
  ZM: '+260',
  ZW: '+263',
}

// Helper to get dial code by country code
export function getDialCode(countryCode: string): string {
  return DIAL_CODES[countryCode] || '+1'
}

// Full list of countries with dial codes
export const COUNTRIES: Country[] = [
  { code: 'AF', name: 'Afghanistan', flag: '🇦🇫', dialCode: '+93' },
  { code: 'AL', name: 'Albania', flag: '🇦🇱', dialCode: '+355' },
  { code: 'DZ', name: 'Algeria', flag: '🇩🇿', dialCode: '+213' },
  { code: 'AD', name: 'Andorra', flag: '🇦🇩', dialCode: '+376' },
  { code: 'AO', name: 'Angola', flag: '🇦🇴', dialCode: '+244' },
  { code: 'AR', name: 'Argentina', flag: '🇦🇷', dialCode: '+54' },
  { code: 'AM', name: 'Armenia', flag: '🇦🇲', dialCode: '+374' },
  { code: 'AU', name: 'Australia', flag: '🇦🇺', dialCode: '+61' },
  {
    code: 'AT',
    name: 'Austria',
    flag: '🇦🇹',
    dialCode: '+43',
    vatPrefix: 'ATU',
  },
  { code: 'AZ', name: 'Azerbaijan', flag: '🇦🇿', dialCode: '+994' },
  { code: 'BS', name: 'Bahamas', flag: '🇧🇸', dialCode: '+1' },
  { code: 'BH', name: 'Bahrain', flag: '🇧🇭', dialCode: '+973' },
  { code: 'BD', name: 'Bangladesh', flag: '🇧🇩', dialCode: '+880' },
  { code: 'BY', name: 'Belarus', flag: '🇧🇾', dialCode: '+375' },
  { code: 'BE', name: 'Belgium', flag: '🇧🇪', dialCode: '+32', vatPrefix: 'BE' },
  { code: 'BZ', name: 'Belize', flag: '🇧🇿', dialCode: '+501' },
  { code: 'BJ', name: 'Benin', flag: '🇧🇯', dialCode: '+229' },
  { code: 'BT', name: 'Bhutan', flag: '🇧🇹', dialCode: '+975' },
  { code: 'BO', name: 'Bolivia', flag: '🇧🇴', dialCode: '+591' },
  { code: 'BA', name: 'Bosnia and Herzegovina', flag: '🇧🇦', dialCode: '+387' },
  { code: 'BW', name: 'Botswana', flag: '🇧🇼', dialCode: '+267' },
  { code: 'BR', name: 'Brazil', flag: '🇧🇷', dialCode: '+55' },
  { code: 'BN', name: 'Brunei', flag: '🇧🇳', dialCode: '+673' },
  {
    code: 'BG',
    name: 'Bulgaria',
    flag: '🇧🇬',
    dialCode: '+359',
    vatPrefix: 'BG',
  },
  { code: 'BF', name: 'Burkina Faso', flag: '🇧🇫', dialCode: '+226' },
  { code: 'BI', name: 'Burundi', flag: '🇧🇮', dialCode: '+257' },
  { code: 'KH', name: 'Cambodia', flag: '🇰🇭', dialCode: '+855' },
  { code: 'CM', name: 'Cameroon', flag: '🇨🇲', dialCode: '+237' },
  { code: 'CA', name: 'Canada', flag: '🇨🇦', dialCode: '+1' },
  { code: 'CV', name: 'Cape Verde', flag: '🇨🇻', dialCode: '+238' },
  {
    code: 'CF',
    name: 'Central African Republic',
    flag: '🇨🇫',
    dialCode: '+236',
  },
  { code: 'TD', name: 'Chad', flag: '🇹🇩', dialCode: '+235' },
  { code: 'CL', name: 'Chile', flag: '🇨🇱', dialCode: '+56' },
  { code: 'CN', name: 'China', flag: '🇨🇳', dialCode: '+86' },
  { code: 'CO', name: 'Colombia', flag: '🇨🇴', dialCode: '+57' },
  { code: 'KM', name: 'Comoros', flag: '🇰🇲', dialCode: '+269' },
  { code: 'CG', name: 'Congo', flag: '🇨🇬', dialCode: '+242' },
  { code: 'CR', name: 'Costa Rica', flag: '🇨🇷', dialCode: '+506' },
  {
    code: 'HR',
    name: 'Croatia',
    flag: '🇭🇷',
    dialCode: '+385',
    vatPrefix: 'HR',
  },
  { code: 'CU', name: 'Cuba', flag: '🇨🇺', dialCode: '+53' },
  { code: 'CY', name: 'Cyprus', flag: '🇨🇾', dialCode: '+357', vatPrefix: 'CY' },
  {
    code: 'CZ',
    name: 'Czech Republic',
    flag: '🇨🇿',
    dialCode: '+420',
    vatPrefix: 'CZ',
  },
  { code: 'DK', name: 'Denmark', flag: '🇩🇰', dialCode: '+45', vatPrefix: 'DK' },
  { code: 'DJ', name: 'Djibouti', flag: '🇩🇯', dialCode: '+253' },
  { code: 'DM', name: 'Dominica', flag: '🇩🇲', dialCode: '+1' },
  { code: 'DO', name: 'Dominican Republic', flag: '🇩🇴', dialCode: '+1' },
  { code: 'EC', name: 'Ecuador', flag: '🇪🇨', dialCode: '+593' },
  { code: 'EG', name: 'Egypt', flag: '🇪🇬', dialCode: '+20' },
  { code: 'SV', name: 'El Salvador', flag: '🇸🇻', dialCode: '+503' },
  { code: 'GQ', name: 'Equatorial Guinea', flag: '🇬🇶', dialCode: '+240' },
  { code: 'ER', name: 'Eritrea', flag: '🇪🇷', dialCode: '+291' },
  {
    code: 'EE',
    name: 'Estonia',
    flag: '🇪🇪',
    dialCode: '+372',
    vatPrefix: 'EE',
  },
  { code: 'ET', name: 'Ethiopia', flag: '🇪🇹', dialCode: '+251' },
  { code: 'FJ', name: 'Fiji', flag: '🇫🇯', dialCode: '+679' },
  {
    code: 'FI',
    name: 'Finland',
    flag: '🇫🇮',
    dialCode: '+358',
    vatPrefix: 'FI',
  },
  { code: 'FR', name: 'France', flag: '🇫🇷', dialCode: '+33', vatPrefix: 'FR' },
  { code: 'GA', name: 'Gabon', flag: '🇬🇦', dialCode: '+241' },
  { code: 'GM', name: 'Gambia', flag: '🇬🇲', dialCode: '+220' },
  { code: 'GE', name: 'Georgia', flag: '🇬🇪', dialCode: '+995' },
  { code: 'DE', name: 'Germany', flag: '🇩🇪', dialCode: '+49', vatPrefix: 'DE' },
  { code: 'GH', name: 'Ghana', flag: '🇬🇭', dialCode: '+233' },
  { code: 'GR', name: 'Greece', flag: '🇬🇷', dialCode: '+30', vatPrefix: 'EL' },
  { code: 'GD', name: 'Grenada', flag: '🇬🇩', dialCode: '+1' },
  { code: 'GT', name: 'Guatemala', flag: '🇬🇹', dialCode: '+502' },
  { code: 'GN', name: 'Guinea', flag: '🇬🇳', dialCode: '+224' },
  { code: 'GW', name: 'Guinea-Bissau', flag: '🇬🇼', dialCode: '+245' },
  { code: 'GY', name: 'Guyana', flag: '🇬🇾', dialCode: '+592' },
  { code: 'HT', name: 'Haiti', flag: '🇭🇹', dialCode: '+509' },
  { code: 'HN', name: 'Honduras', flag: '🇭🇳', dialCode: '+504' },
  { code: 'HK', name: 'Hong Kong', flag: '🇭🇰', dialCode: '+852' },
  { code: 'HU', name: 'Hungary', flag: '🇭🇺', dialCode: '+36', vatPrefix: 'HU' },
  { code: 'IS', name: 'Iceland', flag: '🇮🇸', dialCode: '+354' },
  { code: 'IN', name: 'India', flag: '🇮🇳', dialCode: '+91' },
  { code: 'ID', name: 'Indonesia', flag: '🇮🇩', dialCode: '+62' },
  { code: 'IR', name: 'Iran', flag: '🇮🇷', dialCode: '+98' },
  { code: 'IQ', name: 'Iraq', flag: '🇮🇶', dialCode: '+964' },
  {
    code: 'IE',
    name: 'Ireland',
    flag: '🇮🇪',
    dialCode: '+353',
    vatPrefix: 'IE',
  },
  { code: 'IL', name: 'Israel', flag: '🇮🇱', dialCode: '+972' },
  { code: 'IT', name: 'Italy', flag: '🇮🇹', dialCode: '+39', vatPrefix: 'IT' },
  { code: 'JM', name: 'Jamaica', flag: '🇯🇲', dialCode: '+1' },
  { code: 'JP', name: 'Japan', flag: '🇯🇵', dialCode: '+81' },
  { code: 'JO', name: 'Jordan', flag: '🇯🇴', dialCode: '+962' },
  { code: 'KZ', name: 'Kazakhstan', flag: '🇰🇿', dialCode: '+7' },
  { code: 'KE', name: 'Kenya', flag: '🇰🇪', dialCode: '+254' },
  { code: 'KI', name: 'Kiribati', flag: '🇰🇮', dialCode: '+686' },
  { code: 'KP', name: 'North Korea', flag: '🇰🇵', dialCode: '+850' },
  { code: 'KR', name: 'South Korea', flag: '🇰🇷', dialCode: '+82' },
  { code: 'KW', name: 'Kuwait', flag: '🇰🇼', dialCode: '+965' },
  { code: 'KG', name: 'Kyrgyzstan', flag: '🇰🇬', dialCode: '+996' },
  { code: 'LA', name: 'Laos', flag: '🇱🇦', dialCode: '+856' },
  { code: 'LV', name: 'Latvia', flag: '🇱🇻', dialCode: '+371', vatPrefix: 'LV' },
  { code: 'LB', name: 'Lebanon', flag: '🇱🇧', dialCode: '+961' },
  { code: 'LS', name: 'Lesotho', flag: '🇱🇸', dialCode: '+266' },
  { code: 'LR', name: 'Liberia', flag: '🇱🇷', dialCode: '+231' },
  { code: 'LY', name: 'Libya', flag: '🇱🇾', dialCode: '+218' },
  { code: 'LI', name: 'Liechtenstein', flag: '🇱🇮', dialCode: '+423' },
  {
    code: 'LT',
    name: 'Lithuania',
    flag: '🇱🇹',
    dialCode: '+370',
    vatPrefix: 'LT',
  },
  {
    code: 'LU',
    name: 'Luxembourg',
    flag: '🇱🇺',
    dialCode: '+352',
    vatPrefix: 'LU',
  },
  { code: 'MO', name: 'Macau', flag: '🇲🇴', dialCode: '+853' },
  { code: 'MK', name: 'North Macedonia', flag: '🇲🇰', dialCode: '+389' },
  { code: 'MG', name: 'Madagascar', flag: '🇲🇬', dialCode: '+261' },
  { code: 'MW', name: 'Malawi', flag: '🇲🇼', dialCode: '+265' },
  { code: 'MY', name: 'Malaysia', flag: '🇲🇾', dialCode: '+60' },
  { code: 'MV', name: 'Maldives', flag: '🇲🇻', dialCode: '+960' },
  { code: 'ML', name: 'Mali', flag: '🇲🇱', dialCode: '+223' },
  { code: 'MT', name: 'Malta', flag: '🇲🇹', dialCode: '+356', vatPrefix: 'MT' },
  { code: 'MH', name: 'Marshall Islands', flag: '🇲🇭', dialCode: '+692' },
  { code: 'MR', name: 'Mauritania', flag: '🇲🇷', dialCode: '+222' },
  { code: 'MU', name: 'Mauritius', flag: '🇲🇺', dialCode: '+230' },
  { code: 'MX', name: 'Mexico', flag: '🇲🇽', dialCode: '+52' },
  { code: 'FM', name: 'Micronesia', flag: '🇫🇲', dialCode: '+691' },
  { code: 'MD', name: 'Moldova', flag: '🇲🇩', dialCode: '+373' },
  { code: 'MC', name: 'Monaco', flag: '🇲🇨', dialCode: '+377' },
  { code: 'MN', name: 'Mongolia', flag: '🇲🇳', dialCode: '+976' },
  { code: 'ME', name: 'Montenegro', flag: '🇲🇪', dialCode: '+382' },
  { code: 'MA', name: 'Morocco', flag: '🇲🇦', dialCode: '+212' },
  { code: 'MZ', name: 'Mozambique', flag: '🇲🇿', dialCode: '+258' },
  { code: 'MM', name: 'Myanmar', flag: '🇲🇲', dialCode: '+95' },
  { code: 'NA', name: 'Namibia', flag: '🇳🇦', dialCode: '+264' },
  { code: 'NR', name: 'Nauru', flag: '🇳🇷', dialCode: '+674' },
  { code: 'NP', name: 'Nepal', flag: '🇳🇵', dialCode: '+977' },
  {
    code: 'NL',
    name: 'Netherlands',
    flag: '🇳🇱',
    dialCode: '+31',
    vatPrefix: 'NL',
  },
  { code: 'NZ', name: 'New Zealand', flag: '🇳🇿', dialCode: '+64' },
  { code: 'NI', name: 'Nicaragua', flag: '🇳🇮', dialCode: '+505' },
  { code: 'NE', name: 'Niger', flag: '🇳🇪', dialCode: '+227' },
  { code: 'NG', name: 'Nigeria', flag: '🇳🇬', dialCode: '+234' },
  { code: 'NO', name: 'Norway', flag: '🇳🇴', dialCode: '+47' },
  { code: 'OM', name: 'Oman', flag: '🇴🇲', dialCode: '+968' },
  { code: 'PK', name: 'Pakistan', flag: '🇵🇰', dialCode: '+92' },
  { code: 'PW', name: 'Palau', flag: '🇵🇼', dialCode: '+680' },
  { code: 'PS', name: 'Palestine', flag: '🇵🇸', dialCode: '+970' },
  { code: 'PA', name: 'Panama', flag: '🇵🇦', dialCode: '+507' },
  { code: 'PG', name: 'Papua New Guinea', flag: '🇵🇬', dialCode: '+675' },
  { code: 'PY', name: 'Paraguay', flag: '🇵🇾', dialCode: '+595' },
  { code: 'PE', name: 'Peru', flag: '🇵🇪', dialCode: '+51' },
  { code: 'PH', name: 'Philippines', flag: '🇵🇭', dialCode: '+63' },
  { code: 'PL', name: 'Poland', flag: '🇵🇱', dialCode: '+48', vatPrefix: 'PL' },
  {
    code: 'PT',
    name: 'Portugal',
    flag: '🇵🇹',
    dialCode: '+351',
    vatPrefix: 'PT',
  },
  { code: 'QA', name: 'Qatar', flag: '🇶🇦', dialCode: '+974' },
  { code: 'RO', name: 'Romania', flag: '🇷🇴', dialCode: '+40', vatPrefix: 'RO' },
  { code: 'RU', name: 'Russia', flag: '🇷🇺', dialCode: '+7' },
  { code: 'RW', name: 'Rwanda', flag: '🇷🇼', dialCode: '+250' },
  { code: 'KN', name: 'Saint Kitts and Nevis', flag: '🇰🇳', dialCode: '+1' },
  { code: 'LC', name: 'Saint Lucia', flag: '🇱🇨', dialCode: '+1' },
  {
    code: 'VC',
    name: 'Saint Vincent and the Grenadines',
    flag: '🇻🇨',
    dialCode: '+1',
  },
  { code: 'WS', name: 'Samoa', flag: '🇼🇸', dialCode: '+685' },
  { code: 'SM', name: 'San Marino', flag: '🇸🇲', dialCode: '+378' },
  { code: 'ST', name: 'Sao Tome and Principe', flag: '🇸🇹', dialCode: '+239' },
  { code: 'SA', name: 'Saudi Arabia', flag: '🇸🇦', dialCode: '+966' },
  { code: 'SN', name: 'Senegal', flag: '🇸🇳', dialCode: '+221' },
  { code: 'RS', name: 'Serbia', flag: '🇷🇸', dialCode: '+381' },
  { code: 'SC', name: 'Seychelles', flag: '🇸🇨', dialCode: '+248' },
  { code: 'SL', name: 'Sierra Leone', flag: '🇸🇱', dialCode: '+232' },
  { code: 'SG', name: 'Singapore', flag: '🇸🇬', dialCode: '+65' },
  {
    code: 'SK',
    name: 'Slovakia',
    flag: '🇸🇰',
    dialCode: '+421',
    vatPrefix: 'SK',
  },
  {
    code: 'SI',
    name: 'Slovenia',
    flag: '🇸🇮',
    dialCode: '+386',
    vatPrefix: 'SI',
  },
  { code: 'SB', name: 'Solomon Islands', flag: '🇸🇧', dialCode: '+677' },
  { code: 'SO', name: 'Somalia', flag: '🇸🇴', dialCode: '+252' },
  { code: 'ZA', name: 'South Africa', flag: '🇿🇦', dialCode: '+27' },
  { code: 'SS', name: 'South Sudan', flag: '🇸🇸', dialCode: '+211' },
  { code: 'ES', name: 'Spain', flag: '🇪🇸', dialCode: '+34', vatPrefix: 'ES' },
  { code: 'LK', name: 'Sri Lanka', flag: '🇱🇰', dialCode: '+94' },
  { code: 'SD', name: 'Sudan', flag: '🇸🇩', dialCode: '+249' },
  { code: 'SR', name: 'Suriname', flag: '🇸🇷', dialCode: '+597' },
  { code: 'SZ', name: 'Eswatini', flag: '🇸🇿', dialCode: '+268' },
  { code: 'SE', name: 'Sweden', flag: '🇸🇪', dialCode: '+46', vatPrefix: 'SE' },
  { code: 'CH', name: 'Switzerland', flag: '🇨🇭', dialCode: '+41' },
  { code: 'SY', name: 'Syria', flag: '🇸🇾', dialCode: '+963' },
  { code: 'TW', name: 'Taiwan', flag: '🇹🇼', dialCode: '+886' },
  { code: 'TJ', name: 'Tajikistan', flag: '🇹🇯', dialCode: '+992' },
  { code: 'TZ', name: 'Tanzania', flag: '🇹🇿', dialCode: '+255' },
  { code: 'TH', name: 'Thailand', flag: '🇹🇭', dialCode: '+66' },
  { code: 'TL', name: 'Timor-Leste', flag: '🇹🇱', dialCode: '+670' },
  { code: 'TG', name: 'Togo', flag: '🇹🇬', dialCode: '+228' },
  { code: 'TO', name: 'Tonga', flag: '🇹🇴', dialCode: '+676' },
  { code: 'TT', name: 'Trinidad and Tobago', flag: '🇹🇹', dialCode: '+1' },
  { code: 'TN', name: 'Tunisia', flag: '🇹🇳', dialCode: '+216' },
  { code: 'TR', name: 'Turkey', flag: '🇹🇷', dialCode: '+90' },
  { code: 'TM', name: 'Turkmenistan', flag: '🇹🇲', dialCode: '+993' },
  { code: 'TV', name: 'Tuvalu', flag: '🇹🇻', dialCode: '+688' },
  { code: 'UG', name: 'Uganda', flag: '🇺🇬', dialCode: '+256' },
  { code: 'UA', name: 'Ukraine', flag: '🇺🇦', dialCode: '+380' },
  { code: 'AE', name: 'United Arab Emirates', flag: '🇦🇪', dialCode: '+971' },
  { code: 'GB', name: 'United Kingdom', flag: '🇬🇧', dialCode: '+44' },
  { code: 'US', name: 'United States', flag: '🇺🇸', dialCode: '+1' },
  { code: 'UY', name: 'Uruguay', flag: '🇺🇾', dialCode: '+598' },
  { code: 'UZ', name: 'Uzbekistan', flag: '🇺🇿', dialCode: '+998' },
  { code: 'VU', name: 'Vanuatu', flag: '🇻🇺', dialCode: '+678' },
  { code: 'VA', name: 'Vatican City', flag: '🇻🇦', dialCode: '+39' },
  { code: 'VE', name: 'Venezuela', flag: '🇻🇪', dialCode: '+58' },
  { code: 'VN', name: 'Vietnam', flag: '🇻🇳', dialCode: '+84' },
  { code: 'YE', name: 'Yemen', flag: '🇾🇪', dialCode: '+967' },
  { code: 'ZM', name: 'Zambia', flag: '🇿🇲', dialCode: '+260' },
  { code: 'ZW', name: 'Zimbabwe', flag: '🇿🇼', dialCode: '+263' },
]

// Helper to get country by code
export function getCountryByCode(code: string): Country | undefined {
  return COUNTRIES.find((c) => c.code === code)
}

// Helper to check if a country is in the EU (has VAT prefix)
export function isEuCountry(code: string): boolean {
  return code in EU_VAT_PREFIXES
}

// Get VAT prefix for a country
export function getVatPrefix(code: string): string | undefined {
  return EU_VAT_PREFIXES[code]
}

/**
 * Matches EU VAT ID country prefixes (2-3 uppercase letters at the start).
 * Examples: "DE" (Germany), "FR" (France), "EL" (Greece), "ATU" (Austria)
 */
export const VAT_PREFIX_PATTERN = /^[A-Z]{2,3}/

/**
 * Updates VAT ID when country changes.
 * Handles adding/replacing/removing VAT prefixes based on EU membership.
 *
 * @param currentVatId - The current VAT ID value
 * @param oldCountryCode - The previous country code (ISO 3166-1 alpha-2)
 * @param newCountryCode - The new country code (ISO 3166-1 alpha-2)
 * @returns The updated VAT ID with appropriate prefix handling
 */
export function updateVatIdForCountryChange(
  currentVatId: string,
  oldCountryCode: string,
  newCountryCode: string
): string {
  const newPrefix = getVatPrefix(newCountryCode)
  const oldPrefix = getVatPrefix(oldCountryCode)

  if (newPrefix) {
    // Switching to EU country - add/replace prefix
    if (!currentVatId || !currentVatId.match(VAT_PREFIX_PATTERN)) {
      return newPrefix
    }
    // Replace old prefix with new one
    const vatWithoutPrefix = currentVatId.replace(VAT_PREFIX_PATTERN, '')
    return newPrefix + vatWithoutPrefix
  } else if (oldPrefix && currentVatId) {
    // Switching from EU to non-EU - remove the old prefix
    return currentVatId.replace(new RegExp(`^${oldPrefix}`), '')
  }
  return currentVatId
}

// Default country code for billing (used when no country is set)
export const DEFAULT_COUNTRY = 'US'

/**
 * Countries where Tax ID (VAT/GST) is not typically required on B2B invoices.
 * - US: No federal VAT; state sales tax doesn't require tax ID on invoices
 * - CA: GST/HST exists but typically handled by payment processor
 * - HK: No VAT/GST system
 * - SG: GST registered, but optional for foreign SaaS providers
 */
const COUNTRIES_WITHOUT_TAX_ID = new Set(['US', 'CA', 'HK', 'SG'])

/**
 * Determines whether the Tax ID field should be shown for a given country.
 * Returns true for EU countries (VAT) and other countries that use tax IDs.
 */
export function shouldShowTaxId(countryCode: string): boolean {
  if (!countryCode) return false
  // Show for EU countries (have VAT prefix) or any country not in the exempt list
  return isEuCountry(countryCode) || !COUNTRIES_WITHOUT_TAX_ID.has(countryCode)
}

/**
 * Returns the localized label for postal code based on country.
 * - US: "ZIP code"
 * - GB, AU, NZ: "Postcode"
 * - Default: "Postal code"
 */
export function getPostalCodeLabel(countryCode: string): string {
  switch (countryCode) {
    case 'US':
      return 'ZIP code'
    case 'GB':
    case 'AU':
    case 'NZ':
      return 'Postcode'
    default:
      return 'Postal code'
  }
}

/**
 * Returns the localized label for state/province based on country.
 * - US, AU: "State"
 * - CA: "Province"
 * - GB, IE: "County"
 * - Default: "State / Province"
 */
export function getStateLabel(countryCode: string): string {
  switch (countryCode) {
    case 'US':
    case 'AU':
      return 'State'
    case 'CA':
      return 'Province'
    case 'GB':
    case 'IE':
      return 'County'
    default:
      return 'State / Province'
  }
}
