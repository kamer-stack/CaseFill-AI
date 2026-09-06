/**
 * CaseFill-AI Type Definitions
 */

export type DocType =
  | 'child_picture'
  | 'result_card'
  | 'b_form'
  | 'death_certificate'
  | 'mother_cnic'
  | 'father_cnic'
  | 'address'
  | 'mother_education';

export type UserRole = 'admin' | 'fso' | 'family';
export type AccountType = 'official' | 'family';
export type CaseStatus = 'draft' | 'pending_verification' | 'flagged' | 'verified' | 'rejected' | 'unassigned';
export type DocSlotStatus = 'empty' | 'uploading' | 'extracting' | 'done' | 'error' | 'not_provided';

export interface AppUser {
  id: string;
  name: string;
  cnic: string;
  phone: string;
  email?: string;
  role: UserRole;
  account_type: AccountType;
  designation?: string;
  badge?: string;
  fso_id?: string;
  assigned_region_ids?: string;
  area_address?: string;
  city?: string;
  assigned_region_id?: string;
  created_at?: string;
}

export interface DocumentSlotConfig {
  id: DocType;
  title: string;
  urduTitle: string;
  subtitle: string;
  isInputOnly?: boolean;
  isMandatory: boolean;
  status: DocSlotStatus;
  file?: { name: string; previewUrl: string };
  notProvidedReason?: string;
  errorMessage?: string;
}

export const INITIAL_DOCUMENT_SLOTS: DocumentSlotConfig[] = [
  { id: 'child_picture', title: "Child's Picture", urduTitle: 'یتیم بچے کی تصویر', subtitle: 'Passport-style photo with clear face', isMandatory: true, status: 'empty' },
  { id: 'result_card', title: 'School Result Card', urduTitle: 'اسکول کا نتیجہ نامہ', subtitle: 'Annual progress report', isMandatory: true, status: 'empty' },
  { id: 'b_form', title: "Child's B-Form", urduTitle: 'ب فارم', subtitle: 'Family Registration Certificate', isMandatory: true, status: 'empty' },
  { id: 'death_certificate', title: "Father's Death Certificate", urduTitle: 'والد کا ڈیتھ سرٹیفکیٹ', subtitle: 'Union Council death certificate', isMandatory: true, status: 'empty' },
  { id: 'mother_cnic', title: "Mother's CNIC", urduTitle: 'والدہ کا شناختی کارڈ', subtitle: 'Smart National ID Card', isMandatory: true, status: 'empty' },
  { id: 'father_cnic', title: "Father's CNIC", urduTitle: 'مرحوم والد کا شناختی کارڈ', subtitle: 'Deceased father CNIC (optional)', isMandatory: false, status: 'empty' },
  { id: 'address', title: 'Residential Address', urduTitle: 'رہائشی پتہ', subtitle: 'Current residence', isInputOnly: true, isMandatory: true, status: 'empty' },
  { id: 'mother_education', title: "Mother's Education", urduTitle: 'والدہ کی تعلیم', subtitle: 'Highest schooling level', isInputOnly: true, isMandatory: true, status: 'empty' },
];

export interface CrossCheckResult {
  label: string;
  status: 'MATCH' | 'SIMILAR' | 'MISMATCH' | 'NEEDS_REVIEW' | 'DIFFERENT_SCRIPT';
  detail?: string;
  similarity?: number;
  source?: { doc: string; field: string };
  target?: { doc: string; field: string };
}

export interface RegionConfig {
  id: string;
  name: string;
  urdu_name: string;
  assigned_fso_id: string | null;
  keywords: string;
  active: number;
}

export interface FsoUser {
  id: string;
  name: string;
  cnic?: string;
  email?: string;
  phone: string;
  badge: string;
  assigned_region_ids: string;
  assigned_region_names?: string[];
}

export interface AidTransferEntry {
  date: string;
  amount: number;
  recorded_at?: string;
  recorded_by?: string;
}

export interface CaseRecord {
  id: string;
  case_number: string;
  status: CaseStatus;
  submission_source?: string;
  family_id?: string;
  region_id?: string;
  assigned_fso_id?: string;
  assigned_fso_name?: string;
  routing_confidence?: number;
  routing_reason?: string;
  created_at: string;
  submitted_at?: string;
  verified_at?: string;
  fso_review_notes?: string;
  flag_reason?: string;
  compiled_json?: string;
  compiled?: any;
  child_crc?: string;
  mother_cnic?: string;
  father_cnic?: string;
  average_confidence?: number;
  documents?: Record<string, any>;
  donor_arranged?: boolean;
  aid_transfer_log?: string | AidTransferEntry[];
  child_user_id?: string;
  child_username?: string;
  child_password?: string;
  child_login_generated_at?: string;
  submitted_by_fso_id?: string;
  submitted_by_fso_name?: string;
  verified_by_fso_id?: string;
  verified_by_fso_name?: string;
}
