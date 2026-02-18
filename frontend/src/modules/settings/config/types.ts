/**
 * Configuration Schema Types
 *
 * Defines TypeScript types for configuration-driven settings pages.
 * This enables creating new settings pages by writing config files
 * instead of repetitive React components.
 */

import type { ReactNode } from 'react';

// ==================== Field Configuration ====================

/**
 * Base field configuration shared by all field types
 */
export interface BaseFieldConfig {
  /** Field name (maps to form data key) */
  name: string;
  /** Display label */
  label: string;
  /** Help text shown below field */
  helpText?: string;
  /** Whether field is required */
  required?: boolean;
  /** Whether field is disabled */
  disabled?: boolean;
  /** Placeholder text */
  placeholder?: string;
  /** Custom validation function */
  validate?: (value: any) => string | undefined;
  /** Conditional rendering function */
  condition?: (formData: any, context: any) => boolean;
}

/**
 * Text input field
 */
export interface TextFieldConfig extends BaseFieldConfig {
  type: 'text' | 'password';
  /** Default value */
  defaultValue?: string;
  /** Min length validation */
  minLength?: number;
  /** Max length validation */
  maxLength?: number;
  /** Pattern validation (regex) */
  pattern?: string;
}

/**
 * Number input field
 */
export interface NumberFieldConfig extends BaseFieldConfig {
  type: 'number';
  /** Default value */
  defaultValue?: number;
  /** Minimum value */
  min?: number;
  /** Maximum value */
  max?: number;
  /** Step increment */
  step?: number;
}

/**
 * Select dropdown field
 */
export interface SelectFieldConfig extends BaseFieldConfig {
  type: 'select';
  /** Default value */
  defaultValue?: string;
  /** Static options */
  options?: Array<{ value: string; label: string; disabled?: boolean }>;
  /** Dynamic options from context */
  dynamicOptions?: (context: any) => Array<{ value: string; label: string; disabled?: boolean }>;
  /** Allow empty selection */
  allowEmpty?: boolean;
  /** Empty option label */
  emptyLabel?: string;
}

/**
 * Checkbox field
 */
export interface CheckboxFieldConfig extends BaseFieldConfig {
  type: 'checkbox';
  /** Default value */
  defaultValue?: boolean;
}

/**
 * Slider field
 */
export interface SliderFieldConfig extends BaseFieldConfig {
  type: 'slider';
  /** Default value */
  defaultValue?: number;
  /** Minimum value */
  min: number;
  /** Maximum value */
  max: number;
  /** Step increment */
  step: number;
  /** Show value labels */
  showValue?: boolean;
  /** Custom value formatter */
  formatValue?: (value: number) => string;
  /** Show min/max labels */
  showLabels?: boolean;
  /** Custom min label */
  minLabel?: string;
  /** Custom max label */
  maxLabel?: string;
  /** Allow empty (use provider default) */
  allowEmpty?: boolean;
  /** Empty value label */
  emptyLabel?: string;
}

/**
 * Textarea field
 */
export interface TextareaFieldConfig extends BaseFieldConfig {
  type: 'textarea';
  /** Default value */
  defaultValue?: string;
  /** Number of rows */
  rows?: number;
  /** Min length validation */
  minLength?: number;
  /** Max length validation */
  maxLength?: number;
  /** Use monospace font */
  monospace?: boolean;
}

/**
 * Icon picker field for selecting a Lucide icon
 */
export interface IconPickerFieldConfig extends BaseFieldConfig {
  type: 'icon-picker';
  /** Default value */
  defaultValue?: string;
  /** Number of columns in the icon grid */
  columns?: number;
}

/**
 * Multi-select field for selecting multiple values
 */
export interface MultiSelectFieldConfig extends BaseFieldConfig {
  type: 'multi-select';
  /** Default value */
  defaultValue?: string[];
  /** Static options */
  options?: Array<{ value: string; label: string; disabled?: boolean }>;
  /** Dynamic options from context */
  dynamicOptions?: (context: any) => Array<{ value: string; label: string; disabled?: boolean }>;
}

/**
 * Prompt template variables visual editor
 */
export interface TemplateVariablesFieldConfig extends BaseFieldConfig {
  type: 'template-variables';
  /** Default value */
  defaultValue?: Array<Record<string, any>>;
}

/**
 * Preset field: renders a button group that batch-applies effects to other fields.
 * The preset value itself is NOT persisted -- strip it via `transformSave`.
 */
export interface PresetFieldConfig extends BaseFieldConfig {
  type: 'preset';
  /** Available presets */
  options: Array<{
    /** Unique preset identifier */
    value: string;
    /** Display label */
    label: string;
    /** Short description shown below label */
    description?: string;
    /** Field values to apply when this preset is selected */
    effects: Record<string, any>;
  }>;
}

/**
 * Model ID field with async provider-model discovery.
 * Fetches available models from the provider API and shows them
 * as selectable suggestions alongside a free-text input.
 */
export interface ModelIdFieldConfig extends BaseFieldConfig {
  type: 'model-id';
  /** Default value */
  defaultValue?: string;
  /** Form field that holds the provider ID (default: 'provider_id') */
  providerField?: string;
  /** Form field to auto-fill with the display name (default: 'name') */
  nameField?: string;
}

/**
 * Union type of all field configurations
 */
export type FieldConfig =
  | TextFieldConfig
  | NumberFieldConfig
  | SelectFieldConfig
  | CheckboxFieldConfig
  | SliderFieldConfig
  | TextareaFieldConfig
  | IconPickerFieldConfig
  | MultiSelectFieldConfig
  | TemplateVariablesFieldConfig
  | PresetFieldConfig
  | ModelIdFieldConfig;

// ==================== Table Configuration ====================

/**
 * Table column configuration
 */
export interface TableColumnConfig<T = any> {
  /** Column key (maps to data property) */
  key: string;
  /** Column header label */
  label: string;
  /** Column width (Tailwind class) */
  width?: string;
  /** Custom cell renderer */
  render?: (value: any, row: T, context: any) => ReactNode;
  /** Whether column is sortable */
  sortable?: boolean;
  /** Custom sort function */
  sortFn?: (a: T, b: T) => number;
  /** Whether to hide on mobile */
  hideOnMobile?: boolean;
}

/**
 * Action button configuration
 */
export interface ActionConfig<T = any> {
  /** Action identifier */
  id: string;
  /** Button label or icon */
  label: ReactNode;
  /** Button icon (Heroicon component) */
  icon?: React.ComponentType<{ className?: string }>;
  /** Action handler */
  onClick: (item: T, context: any) => void | Promise<void>;
  /** Whether action is disabled */
  disabled?: (item: T, context: any) => boolean;
  /** Button color variant */
  variant?: 'primary' | 'secondary' | 'danger' | 'warning' | 'success';
  /** Tooltip text */
  tooltip?: string;
  /** Show only on hover */
  showOnHover?: boolean;
  /** Confirm dialog before action */
  confirm?: {
    title: string;
    message: string | ((item: T) => string);
  };
}

// ==================== CRUD Settings Configuration ====================

/**
 * Complete configuration for CRUD settings page
 */
export interface CrudSettingsConfig<T = any> {
  /** Config type identifier */
  type: 'crud';
  /** Page title */
  title: string;
  /** Page description */
  description?: string;
  /** Item name (singular, e.g., "assistant", "model") */
  itemName: string;
  /** Item name plural (defaults to itemName + "s") */
  itemNamePlural?: string;

  // Table configuration
  /** Table columns */
  columns: TableColumnConfig<T>[];
  /** Status field key for enabled/disabled badge */
  statusKey?: string;
  /** Default indicator field key (e.g., "isDefault") */
  defaultKey?: string;
  /** Filter function for search */
  filterFn?: (item: T, searchTerm: string) => boolean;
  /** Enable search */
  enableSearch?: boolean;
  /** Search placeholder */
  searchPlaceholder?: string;

  // Form configuration
  /** Fields for create form */
  createFields: FieldConfig[];
  /** Fields for edit form (defaults to createFields) */
  editFields?: FieldConfig[];
  /** Custom form renderer */
  customFormRenderer?: (
    formData: any,
    setFormData: (data: any) => void,
    context: any,
    isEdit: boolean
  ) => ReactNode;
  /** Create page metadata */
  createPage?: {
    title?: string;
    description?: string;
    backLabel?: string;
    cancelLabel?: string;
    successMessage?: string;
  };
  /** Edit page metadata */
  editPage?: {
    title?: string | ((item: T) => string);
    description?: string | ((item: T) => string);
    backLabel?: string;
    cancelLabel?: string;
    successMessage?: string | ((item: T) => string);
  };
  /** Create UI mode */
  createMode?: 'modal' | 'page';
  /** Create page path */
  createPath?: string;
  /** Edit UI mode */
  editMode?: 'modal' | 'page';
  /** Edit page path builder (used when editMode = "page") */
  editPath?: (itemId: string, item: T) => string;

  // Actions
  /** Row actions */
  rowActions?: ActionConfig<T>[];
  /** Global actions (shown in header) */
  globalActions?: ActionConfig<T>[];
  /** Enable default create/edit/delete actions */
  enableDefaultActions?: {
    create?: boolean;
    edit?: boolean;
    delete?: boolean;
    setDefault?: boolean;
  };
  /** Per-item visibility control for default actions */
  defaultActionVisibility?: {
    edit?: (item: T, context: ConfigContext) => boolean;
    delete?: (item: T, context: ConfigContext) => boolean;
    setDefault?: (item: T, context: ConfigContext) => boolean;
  };

  // Validation
  /** Validate form data before submit */
  validateForm?: (formData: any, isEdit: boolean) => string | undefined;

  // Custom components
  /** Custom empty state */
  emptyState?: ReactNode;
  /** Custom loading state */
  loadingState?: ReactNode;
}

// ==================== Simple Config Settings Configuration ====================

/**
 * API endpoint configuration for simple config
 */
export interface ConfigApiEndpoint {
  /** GET endpoint to load config */
  get: string;
  /** POST endpoint to update config */
  update: string;
}

/**
 * Complete configuration for simple config settings page
 */
export interface SimpleConfigSettingsConfig {
  /** Config type identifier */
  type: 'config';
  /** Page title */
  title: string;
  /** Page description */
  description?: string;

  // API configuration
  /** API endpoints */
  apiEndpoint: ConfigApiEndpoint;

  // Form configuration
  /** Form fields */
  fields: FieldConfig[];
  /** Custom form renderer */
  customFormRenderer?: (
    formData: any,
    setFormData: (data: any) => void,
    context: any
  ) => ReactNode;

  // Validation
  /** Validate form data before submit */
  validateForm?: (formData: any) => string | undefined;

  // Transform functions
  /** Transform data from API response to form state */
  transformLoad?: (data: any) => any;
  /** Transform form state to API request */
  transformSave?: (data: any) => any;

  // Custom actions
  /** Additional action buttons */
  customActions?: Array<{
    label: string;
    icon?: React.ComponentType<{ className?: string }>;
    onClick: (formData: any, context: any) => void | Promise<void>;
    variant?: 'primary' | 'secondary' | 'danger';
  }>;

  // Custom components
  /** Custom loading state */
  loadingState?: ReactNode;
}

// ==================== Context Types ====================

/**
 * Context passed to configuration functions
 * Contains shared state and data needed by forms
 */
export interface ConfigContext {
  /** Available models for model selection */
  models?: any[];
  /** Available assistants */
  assistants?: any[];
  /** Available providers */
  providers?: any[];
  /** Available builtin providers */
  builtinProviders?: any[];
  /** Current user preferences */
  preferences?: any;
  /** Any additional context data */
  [key: string]: any;
}

// ==================== Utility Types ====================

/**
 * Union of all settings config types
 */
export type SettingsConfig = CrudSettingsConfig | SimpleConfigSettingsConfig;

/**
 * Extract item type from CRUD config
 */
export type ExtractItemType<T> = T extends CrudSettingsConfig<infer U> ? U : never;

/**
 * Hook interface for CRUD operations
 */
export interface CrudHook<T> {
  /** Items list */
  items: T[];
  /** Default item ID */
  defaultItemId?: string | null;
  /** Loading state */
  loading: boolean;
  /** Error message */
  error: string | null;
  /** Create item */
  createItem: (item: any) => Promise<void>;
  /** Update item */
  updateItem: (id: string, item: any) => Promise<void>;
  /** Delete item */
  deleteItem: (id: string) => Promise<void>;
  /** Set default item */
  setDefault?: (id: string) => Promise<void>;
  /** Refresh data */
  refreshData: () => Promise<void>;
}
