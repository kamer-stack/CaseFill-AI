/**
 * Edit-time field validation for the review screen.
 * Regex/format rules applied when the FSO commits an edit — extraction-time
 * values are only checked once they are edited. Empty values pass (a field
 * may be deliberately left null when the document is unreadable).
 */

export interface FieldRule {
  test: (value: string) => boolean;
  message: string;
}

const LATIN = /[A-Za-z]/;
const URDU = /[\u0600-\u06FF]/;

const lettersAndSpaces = (label: string): FieldRule => ({
  test: (v) => /^[A-Za-z\u0600-\u06FF\s]+$/.test(v),
  message: `${label} must contain letters and spaces only (no digits or special characters)`,
});

const singleScriptName = (label: string): FieldRule => ({
  test: (v) => {
    if (!/^[A-Za-z\u0600-\u06FF\s]+$/.test(v)) return false;
    // English OR Urdu — mixing scripts within one field is not allowed
    return !(LATIN.test(v) && URDU.test(v));
  },
  message: `${label} must contain letters and spaces only, in English or Urdu — do not mix scripts in one field`,
});

const nnnnnFormat = (label: string): FieldRule => ({
  test: (v) => /^\d{5}-\d{7}-\d$/.test(v),
  message: `${label} must be in format 12345-1234567-1`,
});

const dateRule: FieldRule = {
  test: (v) => {
    const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(v);
    if (!m) return false;
    const day = parseInt(m[1], 10);
    const month = parseInt(m[2], 10);
    const year = parseInt(m[3], 10);
    if (month < 1 || month > 12) return false;
    const leap = (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
    const daysInMonth = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    return day >= 1 && day <= daysInMonth[month - 1];
  },
  message: 'Date must be a valid date in DD-MM-YYYY format',
};

// Top-level fields, keyed by docType then field name.
// Unlisted docs (child_picture, address, mother_education) and unlisted
// fields (class_grade, full_address) intentionally have no rules.
const FIELD_RULES: Record<string, Record<string, FieldRule>> = {
  result_card: {
    child_name: singleScriptName('Child name'),
    school_name: lettersAndSpaces('School name'),
    result_percentage_or_grade: {
      test: (v) => /^[0-9.%]+$/.test(v),
      message: 'Result must contain digits, a decimal point, or % only (no letters)',
    },
    year: {
      test: (v) => /^\d{4}$/.test(v),
      message: 'Year must be exactly 4 digits',
    },
  },
  b_form: {
    crc_number: {
      test: (v) => /^[0-9-]+$/.test(v),
      message: 'CRC number must contain digits and hyphens only',
    },
    applicant_name: singleScriptName('Applicant name'),
    father_name: singleScriptName('Father name'),
    mother_name: singleScriptName('Mother name'),
    applicant_cnic_number: nnnnnFormat('CNIC'),
    father_cnic_number: nnnnnFormat('CNIC'),
    mother_cnic_number: nnnnnFormat('CNIC'),
  },
  death_certificate: {
    deceased_name: lettersAndSpaces('Deceased name'),
    father_or_husband_name: lettersAndSpaces('Father or husband name'),
    date_of_death: dateRule,
    registration_number: {
      test: (v) => /^\d+$/.test(v),
      message: 'Registration number must contain digits only',
    },
    issuing_union_council: lettersAndSpaces('Issuing union council'),
  },
  mother_cnic: {
    name: lettersAndSpaces('Name'),
    father_or_husband_name: lettersAndSpaces('Father or husband name'),
    cnic_number: nnnnnFormat('CNIC'),
    date_of_birth: dateRule,
  },
  father_cnic: {
    name: lettersAndSpaces('Name'),
    father_name: lettersAndSpaces('Father name'),
    cnic_number: nnnnnFormat('CNIC'),
    date_of_birth: dateRule,
  },
};

// Per-child fields inside the B-form children array
const CHILD_FIELD_RULES: Record<string, Record<string, FieldRule>> = {
  b_form: {
    child_name: singleScriptName('Child name'),
    child_registration_number: nnnnnFormat('Child registration number'),
    date_of_birth: dateRule,
  },
};

export function getFieldRule(docType: string, fieldPath: string): FieldRule | null {
  const childMatch = /^children\.\d+\.(.+)$/.exec(fieldPath);
  if (childMatch) {
    return CHILD_FIELD_RULES[docType]?.[childMatch[1]] ?? null;
  }
  return FIELD_RULES[docType]?.[fieldPath] ?? null;
}
